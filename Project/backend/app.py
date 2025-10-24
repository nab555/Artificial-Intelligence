import os
import json
import sys
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "sessions.db")
DATA_JSON_PATH = os.path.join(BASE_DIR, "..", "data", "data.json")
DB_URL = f"sqlite:///{DB_PATH}"

os.makedirs(os.path.join(BASE_DIR, "..", "data"), exist_ok=True)

if os.path.exists(DATA_JSON_PATH):
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        localData = json.load(f)
else:
    localData = {}

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    agent = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    conversation_state = Column(Text, default="{}")

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

def check_and_update_database():
    """Check if database needs to be updated and handle migrations"""
    inspector = inspect(engine)

    if 'sessions' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('sessions')]

        if 'conversation_state' not in existing_columns:
            print("Database schema needs update. Adding missing columns...")

            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        CREATE TABLE sessions_temp (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            agent VARCHAR(256) NOT NULL,
                            created_at DATETIME,
                            conversation_state TEXT DEFAULT '{}'
                        )
                    """))

                    conn.execute(text("""
                        INSERT INTO sessions_temp (id, agent, created_at, conversation_state)
                        SELECT id, agent, created_at, '{}' FROM sessions
                    """))

                    conn.execute(text("DROP TABLE sessions"))

                    conn.execute(text("ALTER TABLE sessions_temp RENAME TO sessions"))

                print("Database schema updated successfully")
            except Exception as e:
                print(f"Database migration failed: {e}")
                print("Creating fresh database...")
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)

    Base.metadata.create_all(bind=engine)
check_and_update_database()


app = Flask(__name__)
CORS(app) 

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

try:
    from openai_client import chat_with_gpt
    OPENAI_AVAILABLE = True
    print("OpenAI client imported successfully")
except ImportError as e:
    print(f"Could not import OpenAI client: {e}")
    OPENAI_AVAILABLE = False
    def chat_with_gpt(messages, model="qwen:1.8b", temperature=0.2, max_tokens=100, **kwargs):
        return "What were you doing during this time?"

class ConversationManager:
    def __init__(self):
        self.question_sequences = {
            "initial": "Why did you edit your start time from {system_start} to {edited_start}?",
            "followup_1": "You mentioned arriving early. What specific activities were you engaged in before your scheduled start time?",
            "followup_2": "Were these activities work-related or personal?",
            "followup_3": "Is there anyone who can verify your early arrival time?",
            "followup_4": "I notice your phone shows {phone_start} but you mentioned {claimed_start}. Can you explain this {difference} minute difference?",
            "followup_5": "How do you typically track your work hours when you arrive early?",
            "verification": "To confirm: You {activity_description}. Is this complete and accurate?"
        }
        self.asked_questions_tracker = {}

    def standardize_time_format(self, time_str):
        """Convert many time formats to consistent h:mm:ss AM/PM or return 'unknown'."""
        if not time_str or str(time_str).strip() == '':
            return 'unknown'

        try:
            s = str(time_str).strip()
            try:
                dt = datetime.fromisoformat(s)
                return dt.strftime("%I:%M:%S %p")
            except Exception:
                pass

            m = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM|am|pm)?', s)
            if m:
                hour = int(m.group(1))
                minute = int(m.group(2))
                second = int(m.group(3)) if m.group(3) else 0
                period = m.group(4)

                if period:
                    period = period.upper()
                    if period == 'PM' and hour != 12:
                        hour += 12
                    if period == 'AM' and hour == 12:
                        hour = 0
                else:
                    if 0 <= hour <= 23:
                        pass  
                    else:
                        
                        return 'unknown'

                disp_hour = hour
                disp_period = 'AM'
                if hour == 0:
                    disp_hour = 12
                    disp_period = 'AM'
                elif hour == 12:
                    disp_hour = 12
                    disp_period = 'PM'
                elif hour > 12:
                    disp_hour = hour - 12
                    disp_period = 'PM'
                else:
                    disp_period = 'AM'

                return f"{disp_hour:02d}:{minute:02d}:{second:02d} {disp_period}"

            m2 = re.search(r'^\d{1,4}$', s)
            if m2:
                val = s
                if len(val) in (3,4):
                    minute_part = val[-2:]
                    hour_part = val[:-2]
                    hour = int(hour_part)
                    minute = int(minute_part)
                    return self.standardize_time_format(f"{hour}:{minute}:00")
                elif len(val) <= 2:
                    hour = int(val)
                    return self.standardize_time_format(f"{hour}:00:00")

            return 'unknown'

        except Exception as e:
            print(f"Time standardization error: {e}")
            return 'unknown'

    def get_time_difference(self, time1_str, time2_str):
        """Calculate time difference in minutes between two time strings. Returns int or None."""
        if not time1_str or not time2_str:
            return None

        try:
            def parse_time_to_minutes(time_str):
                standardized = self.standardize_time_format(time_str)
                if standardized == 'unknown':
                    return None
                parts = standardized.split(' ')
                time_part = parts[0]
                period = parts[1] if len(parts) > 1 else 'AM'

                hours, minutes, seconds = map(int, time_part.split(':'))

                if period.upper() == 'PM' and hours != 12:
                    hours += 12
                elif period.upper() == 'AM' and hours == 12:
                    hours = 0

                return hours * 60 + minutes

            t1 = parse_time_to_minutes(time1_str)
            t2 = parse_time_to_minutes(time2_str)

            if t1 is None or t2 is None:
                return None

            return abs(t1 - t2)

        except Exception as e:
            print(f"Time difference calculation error: {e}")
            return None

    def analyze_conversation_state(self, messages, agent_context, session_id):
        """Analyze current conversation state and determine next action"""
        user_messages = [msg["content"] for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg["content"] for msg in messages if msg["role"] == "assistant"]
        
        question_count = sum(1 for msg in assistant_messages if msg.strip().endswith('?'))
        
        if session_id not in self.asked_questions_tracker:
            self.asked_questions_tracker[session_id] = {
                "asked_questions": [],
                "established_facts": set(),
                "unresolved_issues": set()
            }
        
        tracker = self.asked_questions_tracker[session_id]
        
        state = {
            "established_facts": list(tracker["established_facts"]),
            "unresolved_issues": list(tracker["unresolved_issues"]),
            "remaining_questions": [],
            "conversation_stage": "initial",
            "quality_score": 0,
            "question_count": question_count,
            "last_question_asked": assistant_messages[-1] if assistant_messages else "",
            "asked_questions": tracker["asked_questions"]
        }

        recent_user_text = " ".join(user_messages[-3:]).lower() if user_messages else ""
        all_user_text = " ".join(user_messages).lower()

        if any(word in all_user_text for word in ["meeting", "training", "session", "conference", "briefing", "workshop"]):
            tracker["established_facts"].add("was_in_activity")
        
        time_pattern = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?', recent_user_text)
        if (time_pattern or any(word in recent_user_text for word in 
            ["arrived", "came", "reached", "started", "clocked", "entered", "early", "before"])):
            tracker["established_facts"].add("stated_arrival_time")
        
        if any(word in recent_user_text for word in ["supervisor", "manager", "team lead", "organized", "lead", "headed", "colleague", "coworker"]):
            tracker["established_facts"].add("mentioned_organizer")
        
        if any(word in recent_user_text for word in ["minutes", "hours", "duration", "lasted", "until", "from", "about"]):
            tracker["established_facts"].add("provided_duration")
        
        if any(word in recent_user_text for word in ["topic", "about", "purpose", "discuss", "agenda", "subject", "work", "preparation"]):
            tracker["established_facts"].add("mentioned_purpose")
        
        if any(word in recent_user_text for word in ["glitch", "error", "technical", "issue", "problem", "malfunction", "wrong", "incorrect", "faulty"]):
            tracker["established_facts"].add("explained_phone_discrepancy")
            if "phone_vs_edited_discrepancy" in tracker["unresolved_issues"]:
                tracker["unresolved_issues"].remove("phone_vs_edited_discrepancy")

        state["established_facts"] = list(tracker["established_facts"])
        state["unresolved_issues"] = list(tracker["unresolved_issues"])

        phone_time = self.standardize_time_format(agent_context.get('phone', {}).get('start_time', ''))
        system_time = self.standardize_time_format(agent_context.get('system', {}).get('start_time', ''))
        edited_time = self.standardize_time_format(agent_context.get('agent_disputed', {}).get('start_time', ''))

        phone_edited_diff = self.get_time_difference(phone_time, edited_time)
        if (phone_edited_diff is not None and phone_edited_diff > 0 and 
            "explained_phone_discrepancy" not in tracker["established_facts"]):
            tracker["unresolved_issues"].add("phone_vs_edited_discrepancy")

        system_edited_diff = self.get_time_difference(system_time, edited_time)
        if system_edited_diff is not None and system_edited_diff > 0 and "explained_system_discrepancy" not in tracker["established_facts"]:
            tracker["unresolved_issues"].add("system_vs_edited_discrepancy")

        required_facts = ["was_in_activity", "stated_arrival_time", "mentioned_organizer", "provided_duration", "mentioned_purpose"]
        for fact in required_facts:
            if fact not in state["established_facts"]:
                state["remaining_questions"].append(fact)

        state["quality_score"] = len(state["established_facts"]) * 20

        if len(state["established_facts"]) >= 4 and len(state["unresolved_issues"]) == 0:
            state["conversation_stage"] = "verification"
        elif len(state["established_facts"]) >= 2:
            state["conversation_stage"] = "investigation"
        else:
            state["conversation_stage"] = "initial"

        return state

    def build_activity_description(self, conversation_state, agent_context):
        """Build a summary description for verification"""
        parts = []

        if "was_in_activity" in conversation_state["established_facts"]:
            parts.append("were engaged in preparatory work activities")

        edited_time = self.standardize_time_format(agent_context.get('agent_disputed', {}).get('start_time', ''))
        if edited_time != 'unknown':
            parts.append(f"starting at {edited_time}")

        if "provided_duration" in conversation_state["established_facts"]:
            parts.append("prior to your scheduled start time")

        return " ".join(parts) if parts else "arrived early and were engaged in work activities"

    def should_end_conversation(self, conversation_state, recent_user_input=""):
        """Determine if conversation should end based on completeness"""
        if conversation_state.get("question_count", 0) >= 5:
            return True
        if conversation_state["conversation_stage"] == "verification":
            recent_lower = recent_user_input.lower()
            if any(confirm_word in recent_lower for confirm_word in ["yes", "correct", "accurate", "confirm", "right", "true", "yeah", "yep"]):
                return True

        if conversation_state["quality_score"] >= 60 and len(conversation_state["unresolved_issues"]) == 0:
            return True

        return False

    def generate_conversation_summary(self, messages, agent_context):
        """Generate a dynamic summary based on actual conversation content"""
        user_messages = [msg["content"] for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg["content"] for msg in messages if msg["role"] == "assistant"]
        
        key_points = []
        
        for i, (user_msg, assistant_msg) in enumerate(zip(user_messages, assistant_messages)):
            user_lower = user_msg.lower()
            
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?', user_msg)
            if time_match and "arrival time" not in str(key_points).lower():
                hour = time_match.group(1)
                minute = time_match.group(2) or '00'
                period = (time_match.group(3) or 'AM').upper()
                key_points.append(f"Arrival time: {hour}:{minute} {period}")
            
            if any(word in user_lower for word in ["meeting", "conference", "briefing"]):
                key_points.append("Reason: Scheduled meeting")
            elif any(word in user_lower for word in ["glitch", "error", "technical", "system wrong"]):
                key_points.append("Reason: Technical/system issues")
            elif any(word in user_lower for word in ["early", "before time", "arrived early"]):
                key_points.append("Reason: Early arrival for preparation")
            
            if any(word in user_lower for word in ["work", "preparation", "routine", "task"]):
                if "Activities:" not in str(key_points):
                    key_points.append("Activities: Work-related tasks")
            
            if any(word in user_lower for word in ["no one", "nobody", "alone", "verify"]):
                key_points.append("Verification: No witnesses mentioned")
            elif any(word in user_lower for word in ["supervisor", "manager", "colleague", "team"]):
                key_points.append("Verification: Colleagues involved")
        
        seen = set()
        unique_key_points = []
        for point in key_points:
            if point not in seen:
                seen.add(point)
                unique_key_points.append(point)
        
        edited_start = self.standardize_time_format(agent_context.get('agent_disputed', {}).get('start_time', ''))
        system_start = self.standardize_time_format(agent_context.get('system', {}).get('start_time', ''))
        
        summary_lines = ["CONVERSATION SUMMARY:"]
        
        if edited_start != 'unknown' and system_start != 'unknown':
            time_diff = self.get_time_difference(edited_start, system_start)
            if time_diff:
                summary_lines.append(f"Time edit: {system_start} → {edited_start} ({time_diff} min difference)")
        
        summary_lines.extend(unique_key_points[-4:]) 
        
        summary_lines.append("Information recorded for review.")
        
        return "\n".join(summary_lines)

    def generate_intelligent_question(self, conversation_state, agent_context, recent_user_input="", session_id=""):
        """Generate contextual questions that follow the conversation flow"""
        
        if conversation_state["conversation_stage"] == "verification":
            activity_desc = self.build_activity_description(conversation_state, agent_context)
            return self.question_sequences["verification"].format(activity_description=activity_desc)

        if conversation_state.get("question_count", 0) >= 5:
            return "SUMMARY_REQUEST"

        tracker = self.asked_questions_tracker.get(session_id, {"asked_questions": []})
        
        contextual_question = self.generate_contextual_followup(recent_user_input, tracker, agent_context)
        
        if contextual_question:
            tracker["asked_questions"].append(contextual_question)
            return contextual_question

        return self.generate_fallback_question(conversation_state, agent_context, session_id)

    def generate_contextual_followup(self, user_input, tracker, agent_context):
        """Generate a question that directly follows from the user's last response"""
        
        if not user_input:
            return None
            
        user_input_lower = user_input.lower()
        
        contextual_followups = {
            "system.*wrong|phone.*wrong": [
                "What makes you think the system and phone recordings are incorrect?",
                "How did you determine your actual start time if both system and phone are wrong?",
                "Do you have any other way to verify your arrival time?"
            ],
            "daily routine|normal routine|regular routine": [
                "Could you describe what your daily routine involves when you first arrive?",
                "What specific tasks are part of your morning routine at the office?",
                "When you say 'daily routine', what work activities does that typically include?"
            ],
            "not specific|nothing specific|just routine": [
                "Let me be more specific - were you checking emails, preparing equipment, or something else?",
                "What's the first work-related task you typically complete when you arrive early?",
                "Could you give an example of what you might do during this early arrival time?"
            ],
            "security|face scan|building.*enter": [
                "Does the building security system provide any timestamp confirmation of your arrival?",
                "If you use face scan for tracking, why do you think it didn't record your early arrival?",
                "Can the security system logs verify your entry time?"
            ],
            "no one|nobody|alone": [
                "Since no one was present, how do you typically document your early start times for record-keeping?",
                "What process do you follow to ensure early arrivals are properly recorded when working alone?",
                "Do you use any digital tools or apps to track your time when arriving before others?"
            ],
            "meeting|conference|briefing": [
                "Who organized this meeting and what was its purpose?",
                "Was this meeting scheduled in advance or was it impromptu?",
                "How long did the meeting last and who else attended?"
            ],
            "glitch|error|technical|issue|problem": [
                "Have you experienced similar technical issues with the time tracking system before?",
                "Did you report this technical issue to IT or your supervisor?",
                "What steps did you take to address the technical problem you mentioned?"
            ],
            "early|before.*time|arrived.*early": [
                "What was the reason for arriving early today specifically?",
                "Did you have any urgent tasks that required early preparation?",
                "Is arriving early part of your regular schedule or was this unusual?"
            ]
        }
        
        for pattern, questions in contextual_followups.items():
            if re.search(pattern, user_input_lower):
                available_questions = []
                for q in questions:
                    question_already_asked = False
                    for asked_q in tracker["asked_questions"]:
                        if self.are_questions_similar(q, asked_q):
                            question_already_asked = True
                            break
                    if not question_already_asked:
                        available_questions.append(q)
                
                if available_questions:
                    return available_questions[0]
        
        return None

    def are_questions_similar(self, question1, question2):
        """Check if two questions are similar in meaning"""
        if not question1 or not question2:
            return False
            
        q1_lower = question1.lower()
        q2_lower = question2.lower()
        
        similar_phrases = [
            "what.*activity", "work.*related", "personal",
            "who.*verify", "anyone.*verify", "witness",
            "how.*track", "track.*work", "record.*time",
            "what.*routine", "daily.*routine", "morning.*routine",
            "technical.*issue", "system.*wrong", "phone.*wrong"
        ]
        
        for phrase in similar_phrases:
            if re.search(phrase, q1_lower) and re.search(phrase, q2_lower):
                return True
        
        return False

    def generate_fallback_question(self, conversation_state, agent_context, session_id):
        """Fallback to the original logic if no contextual question fits"""
        tracker = self.asked_questions_tracker.get(session_id, {"asked_questions": []})
        asked_questions = tracker["asked_questions"]

        if ("phone_vs_edited_discrepancy" in conversation_state["unresolved_issues"] and
            not any("phone shows" in q.lower() for q in asked_questions)):
            
            phone_time = self.standardize_time_format(agent_context.get('phone', {}).get('start_time', ''))
            edited_time = self.standardize_time_format(agent_context.get('agent_disputed', {}).get('start_time', ''))
            difference = self.get_time_difference(phone_time, edited_time) or 'some'
            
            question = self.question_sequences["followup_4"].format(
                phone_start=phone_time,
                claimed_start=edited_time,
                difference=difference
            )
            tracker["asked_questions"].append(question)
            return question

        if (not any("why did you edit" in q.lower() for q in asked_questions) and
            "stated_arrival_time" not in conversation_state["established_facts"]):
            
            system_start = self.standardize_time_format(agent_context.get('system', {}).get('start_time', ''))
            edited_start = self.standardize_time_format(agent_context.get('agent_disputed', {}).get('start_time', ''))
            
            if system_start != 'unknown' and edited_start != 'unknown':
                question = self.question_sequences["initial"].format(
                    system_start=system_start,
                    edited_start=edited_start
                )
                tracker["asked_questions"].append(question)
                return question

        question_flow = [
            ("was_in_activity", self.question_sequences["followup_1"]),
            ("mentioned_purpose", self.question_sequences["followup_2"]),
            ("mentioned_organizer", self.question_sequences["followup_3"]),
            ("provided_duration", self.question_sequences["followup_5"])
        ]

        for fact_key, question_template in question_flow:
            if (fact_key not in conversation_state["established_facts"] and
                not any(question_template.split('?')[0].lower() in q.lower() for q in asked_questions)):
                
                tracker["asked_questions"].append(question_template)
                return question_template

        return "SUMMARY_REQUEST"

def is_similar_question(question1, question2):
    """Check if two questions are similar in meaning"""
    key_phrases = [
        "why did you edit", 
        "phone shows", 
        "explain this difference",
        "what activities",
        "who organized",
        "how long",
        "can verify",
        "work-related"
    ]
    
    q1_lower = question1.lower()
    q2_lower = question2.lower()
    
    for phrase in key_phrases:
        if phrase in q1_lower and phrase in q2_lower:
            return True
    return False

conv_manager = ConversationManager()

def format_time_display(time_str):
    """Format time for display using standardized format"""
    return conv_manager.standardize_time_format(time_str)

def get_time_difference(time1_str, time2_str):
    """Calculate time difference using conversation manager"""
    return conv_manager.get_time_difference(time1_str, time2_str)

def generate_initial_question(agent_name, schedule, system_data, phone, agent_disputed):
    """Generate dynamic initial question based on time discrepancy scenario"""
    
    scheduled_start = format_time_display(schedule.get('start_time')) if schedule else 'unknown'
    system_start = format_time_display(system_data.get('start_time')) if system_data else 'unknown'
    phone_start = format_time_display(phone.get('start_time')) if phone else 'unknown'
    agent_edited_start = format_time_display(agent_disputed.get('start_time')) if agent_disputed else 'unknown'
    
    start_time_diff = get_time_difference(agent_edited_start, system_start)
    phone_system_diff = get_time_difference(phone_start, system_start)
    phone_edited_diff = get_time_difference(phone_start, agent_edited_start)
    
    scenario = analyze_time_scenario(system_start, phone_start, agent_edited_start, start_time_diff, phone_system_diff, phone_edited_diff)
    
    context_lines = build_context_lines(agent_name, schedule, system_data, phone, agent_disputed, start_time_diff)
    
    question = generate_scenario_based_question(scenario, system_start, phone_start, agent_edited_start, start_time_diff, phone_edited_diff)
    context_lines.append(f"\n{question}")
    
    return "\n".join(context_lines)

def analyze_time_scenario(system_start, phone_start, agent_edited_start, start_time_diff, phone_system_diff, phone_edited_diff):
    """Analyze the time discrepancy scenario"""
    
    if system_start == 'unknown' and agent_edited_start != 'unknown':
        return "missing_system_time"
    
    if phone_start == 'unknown' and agent_edited_start != 'unknown':
        return "missing_phone_time"
    
    if start_time_diff and start_time_diff > 30:
        if phone_edited_diff and phone_edited_diff > 15:
            return "large_discrepancy_both"
        elif phone_system_diff and phone_system_diff < 5:
            return "system_vs_edited_large"
        else:
            return "significant_edit"
    
    elif start_time_diff and start_time_diff > 15:
        if phone_edited_diff and phone_edited_diff < 10:
            return "phone_supports_edit"
        else:
            return "moderate_edit"
    
    elif phone_start != 'unknown' and phone_edited_diff and phone_edited_diff > 20:
        return "phone_disagrees"
    
    else:
        return "general_inquiry"

def generate_scenario_based_question(scenario, system_start, phone_start, agent_edited_start, start_time_diff, phone_edited_diff):
    """Generate question based on the specific scenario"""
    
    questions = {
        "large_discrepancy_both": f"I notice you changed your start time from {system_start} to {agent_edited_start} ({start_time_diff} minutes), and your phone shows {phone_start}. Can you walk me through what happened during this time period?",
        
        "system_vs_edited_large": f"You've edited your start time from {system_start} to {agent_edited_start} - a difference of {start_time_diff} minutes. What were you doing during this extended period before your scheduled start?",
        
        "significant_edit": f"I see you adjusted your start time by {start_time_diff} minutes from the system-recorded {system_start} to {agent_edited_start}. What prompted this significant change to your recorded time?",
        
        "phone_supports_edit": f"Your phone data shows {phone_start}, which is closer to your edited time of {agent_edited_start} than the system time of {system_start}. What explains the difference between your phone and system recordings?",
        
        "moderate_edit": f"You edited your start time from {system_start} to {agent_edited_start}. Could you explain the reason for this {start_time_diff}-minute adjustment?",
        
        "phone_disagrees": f"Your phone recorded {phone_start}, but you've entered {agent_edited_start} - a difference of {phone_edited_diff} minutes. What accounts for this discrepancy with your phone data?",
        
        "missing_system_time": f"You've entered your start time as {agent_edited_start}, but the system didn't capture an automatic time. Could you describe how you tracked your arrival and what you were working on initially?",
        
        "missing_phone_time": f"You recorded your start time as {agent_edited_start} compared to the system time of {system_start}. Without phone data available, how did you determine and verify your actual arrival time?",
        
        "general_inquiry": f"I'm reviewing your time entry of {agent_edited_start} compared to the system time of {system_start}. Could you provide some context about your activities around this time?"
    }
    
    return questions.get(scenario, f"Could you explain the difference between your recorded start time {agent_edited_start} and the system time {system_start}?")

def build_context_lines(agent_name, schedule, system_data, phone, agent_disputed, start_time_diff):
    """Build the context part (your existing code)"""
    def extract_date(time_str):
        if not time_str or time_str == 'unknown':
            return 'N/A'
        try:
            date_part = time_str.split(' ')[0]
            from datetime import datetime
            dt = datetime.strptime(date_part, '%m/%d/%Y')
            return dt.strftime('%B %d, %Y')
        except:
            return 'N/A'

    shift_date = extract_date(schedule.get('start_time') if schedule else None)
    
    scheduled_start = format_time_display(schedule.get('start_time')) if schedule else 'unknown'
    scheduled_end = format_time_display(schedule.get('end_time')) if schedule else 'unknown'
    system_start = format_time_display(system_data.get('start_time')) if system_data else 'unknown'
    system_end = format_time_display(system_data.get('end_time')) if system_data else 'unknown'
    phone_start = format_time_display(phone.get('start_time')) if phone else 'unknown'
    phone_end = format_time_display(phone.get('end_time')) if phone else 'unknown'
    agent_edited_start = format_time_display(agent_disputed.get('start_time')) if agent_disputed else 'unknown'
    agent_edited_end = format_time_display(agent_disputed.get('end_time')) if agent_disputed else 'unknown'

    context_lines = [
        f"Hi {agent_name},",
        "",
        f"I am reviewing your work session for {shift_date}.",
        "",
        # f"Shift Date: {shift_date}",
        # "",
        # f"Scheduled Start: {scheduled_start}",
        # f"Scheduled End: {scheduled_end}",
        # "",
        # f"System captured Start time: {system_start}",
        # f"System captured End time: {system_end}",
        # "",
        # f"Phone recorded Start time: {phone_start}",
        # f"Phone recorded End time: {phone_end}",
        # "",
        # f"Your edited start time: {agent_edited_start}",
        # f"Your edited end time: {agent_edited_end}",
        # ""
    ]

    if isinstance(start_time_diff, int):
        context_lines.append(f"You edited your start time by {start_time_diff} minutes.")
    
    return context_lines

@app.route("/data", methods=["GET"])
def get_json_data():
    return jsonify(localData)

@app.route("/create_session", methods=["POST"])
def create_session():
    body = request.get_json() or {}
    agent = body.get("agent", "unknown")
    db = SessionLocal()
    s = ChatSession(agent=agent)
    db.add(s)
    db.commit()
    db.refresh(s)
    db.close()
    return jsonify({"id": s.id, "agent": s.agent, "created_at": s.created_at.isoformat()}), 201

@app.route("/sessions/<int:session_id>/messages", methods=["POST"])
def add_message(session_id):
    body = request.get_json() or {}
    role = body.get("role", "user")
    content = body.get("content", "")
    ts = body.get("created_at")
    db = SessionLocal()
    s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not s:
        db.close()
        return jsonify({"error": "session not found"}), 404
    if ts:
        try:
            created_at = datetime.fromisoformat(ts)
        except:
            created_at = datetime.utcnow()
    else:
        created_at = datetime.utcnow()
    msg = ChatMessage(session_id=session_id, role=role, content=content, created_at=created_at)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    db.close()
    return jsonify({"message_id": msg.id, "session_id": session_id}), 201

@app.route("/sessions", methods=["GET"])
def list_sessions():
    db = SessionLocal()
    try:
        sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()
        out = []
        for s in sessions:
            last_msg = None
            if s.messages:
                last_msg = max(s.messages, key=lambda m: m.created_at).created_at.isoformat()
            out.append({
                "id": s.id,
                "agent": s.agent,
                "created_at": s.created_at.isoformat(),
                "last_message_at": last_msg
            })
        db.close()
        return jsonify(out)
    except Exception as e:
        db.close()
        print(f"Error listing sessions: {e}")
        return jsonify({"error": "Database error occurred"}), 500

@app.route("/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id):
    db = SessionLocal()
    try:
        s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not s:
            db.close()
            return jsonify({"error": "session not found"}), 404
        messages = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            } for m in sorted(s.messages, key=lambda mm: mm.created_at)
        ]
        out = {
            "id": s.id,
            "agent": s.agent,
            "created_at": s.created_at.isoformat(),
            "messages": messages
        }
        db.close()
        return jsonify(out)
    except Exception as e:
        db.close()
        print(f"Error getting session: {e}")
        return jsonify({"error": "Database error occurred"}), 500

@app.route("/chat_with_ai", methods=["POST"])
def chat_with_ai():
    """AI chat endpoint with STRICT conversation management"""
    try:
        body = request.get_json() or {}
        messages = body.get("messages", [])
        session_id = body.get("session_id")
        agent_name = body.get("agent_name", "")

        if not messages or not session_id:
            return jsonify({"error": "No messages or session_id provided"}), 400

        db = SessionLocal()
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            db.close()
            return jsonify({"error": "Session not found"}), 404

        agents = localData.get("agents", [])
        agent_context = next((a for a in agents if a.get("name", "").lower() == agent_name.lower()), {}) if agent_name else {}

        conversation_state = conv_manager.analyze_conversation_state(messages, agent_context, session_id)

        recent_user_input = ""
        if messages and messages[-1]["role"] == "user":
            recent_user_input = messages[-1]["content"]

        next_question = conv_manager.generate_intelligent_question(
            conversation_state, agent_context, recent_user_input, session_id
        )

        if (next_question == "SUMMARY_REQUEST" or 
            conv_manager.should_end_conversation(conversation_state, recent_user_input) or 
            conversation_state.get('question_count', 0) >= 5):
            
            summary = conv_manager.generate_conversation_summary(messages, agent_context)
            
            confirmation_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=summary,
                created_at=datetime.utcnow()
            )
            db.add(confirmation_msg)
            db.commit()
            db.close()
            return jsonify({"response": summary})

        system_prompt = f"""You are Quartz AI conducting a professional time discrepancy investigation.

CONVERSATION CONTEXT:
- Question {conversation_state.get('question_count', 1)} of maximum 5
- User's last response: "{recent_user_input}"
- Already established: {conversation_state['established_facts']}

CRITICAL INSTRUCTIONS:
1. DO NOT repeat any previous questions
2. Ask ONLY this specific question: "{next_question}"
3. Keep the question professional and concise
4. Do not add any extra text, explanations, or greetings

OUTPUT ONLY this question: {next_question}"""

        enhanced_messages = [{"role": "system", "content": system_prompt}]
        enhanced_messages.extend(messages[-2:])  

        if OPENAI_AVAILABLE:
            try:
                response = chat_with_gpt(
                    enhanced_messages,
                    temperature=0.1,
                    max_tokens=50,
                    top_p=0.2
                )
            except Exception as e:
                print(f"OpenAI API error: {e}")
                response = next_question
        else:
            response = next_question

        response = (response or "").strip()

        previous_assistant_messages = [msg["content"] for msg in messages if msg["role"] == "assistant"]
        is_repetitive = any(
            prev_msg and response and 
            (prev_msg.lower() == response.lower() or 
             is_similar_question(prev_msg, response))
            for prev_msg in previous_assistant_messages
        )

        if (not response or len(response) < 8 or '?' not in response or is_repetitive):
            response = next_question

        if session_id in conv_manager.asked_questions_tracker:
            conv_manager.asked_questions_tracker[session_id]["asked_questions"].append(response)

        ai_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=response,
            created_at=datetime.utcnow()
        )
        db.add(ai_msg)
        db.commit()
        db.close()

        return jsonify({"response": response})

    except Exception as e:
        print(f"Error in chat_with_ai: {str(e)}")
        return jsonify({"response": "Could you please provide more details about the time discrepancy?"})

@app.route("/agents", methods=["GET"])
def get_agents():
    """Get list of all available agents"""
    agents = localData.get("agents", [])
    agent_list = [{"name": agent.get("name"), "agent_id": agent.get("agent_id")} for agent in agents]
    return jsonify(agent_list)

@app.route("/agent/<agent_name>", methods=["GET"])
def get_agent_details(agent_name):
    """Get detailed information for a specific agent"""
    agents = localData.get("agents", [])
    agent = next((a for a in agents if a.get("name", "").lower() == agent_name.lower()), None)

    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    return jsonify(agent)

@app.route("/initialize_session/<int:session_id>", methods=["POST"])
def initialize_session(session_id):
    """Initialize session with proper context and clear time information"""
    try:
        body = request.get_json() or {}
        agent_name = body.get("agent_name", "")

        if not agent_name:
            return jsonify({"error": "Agent name required"}), 400

        agents = localData.get("agents", [])
        agent_details = next((a for a in agents if a.get("name", "").lower() == agent_name.lower()), None)

        if not agent_details:
            return jsonify({"error": "Agent not found"}), 404

        schedule = agent_details.get("schedule", {})
        system_data = agent_details.get("system", {})
        phone = agent_details.get("phone", {})
        agent_disputed = agent_details.get("agent_disputed", {})

        initial_question = generate_initial_question(agent_name, schedule, system_data, phone, agent_disputed)

        db = SessionLocal()
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            db.close()
            return jsonify({"error": "Session not found"}), 404

        last_assistant = None
        if session.messages:
            sorted_msgs = sorted(session.messages, key=lambda mm: mm.created_at)
            for m in reversed(sorted_msgs):
                if m.role == "assistant":
                    last_assistant = m.content
                    break

        if last_assistant != initial_question:
            ai_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=initial_question,
                created_at=datetime.utcnow()
            )
            db.add(ai_msg)

        conversation_state = conv_manager.analyze_conversation_state([], agent_details, session_id)
        session.conversation_state = json.dumps(conversation_state)

        db.commit()
        db.close()

        return jsonify({
            "success": True,
            "ai_response": initial_question,
            "conversation_state": conversation_state
        })

    except Exception as e:
        print(f"Error initializing session: {str(e)}")

        fallback_message = f"Hi {body.get('agent_name', 'Agent')}, I'm reviewing your session time entries. Could you please explain any differences between your recorded times and the system times?"

        return jsonify({
            "success": True,
            "ai_response": fallback_message
        })

@app.route("/initialize_session", methods=["POST", "OPTIONS"])
def initialize_session_new():
    """New endpoint that matches frontend expectation - creates and initializes in one call"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        body = request.get_json() or {}
        agent_name = body.get("agent_name", "")

        if not agent_name:
            return jsonify({"error": "Agent name required"}), 400

        db = SessionLocal()
        session = ChatSession(agent=agent_name)
        db.add(session)
        db.commit()
        db.refresh(session)
        
        session_id = session.id

        agents = localData.get("agents", [])
        agent_details = next((a for a in agents if a.get("name", "").lower() == agent_name.lower()), None)

        if not agent_details:
            db.close()
            return jsonify({"error": "Agent not found"}), 404

        schedule = agent_details.get("schedule", {})
        system_data = agent_details.get("system", {})
        phone = agent_details.get("phone", {})
        agent_disputed = agent_details.get("agent_disputed", {})

        initial_question = generate_initial_question(agent_name, schedule, system_data, phone, agent_disputed)

        ai_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=initial_question,
            created_at=datetime.utcnow()
        )
        db.add(ai_msg)

        conversation_state = conv_manager.analyze_conversation_state([], agent_details, session_id)
        session.conversation_state = json.dumps(conversation_state)

        db.commit()
        db.close()

        return jsonify({
            "session_id": session_id,
            "message": "Session started successfully",
            "ai_response": initial_question
        })

    except Exception as e:
        print(f"Error in initialize_session: {str(e)}")
        return jsonify({"error": "Failed to initialize session"}), 500

@app.route("/conversation_analysis/<int:session_id>", methods=["GET"])
def get_conversation_analysis(session_id):
    """Get analysis of current conversation state"""
    try:
        db = SessionLocal()
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            db.close()
            return jsonify({"error": "Session not found"}), 404

        messages = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            } for m in sorted(session.messages, key=lambda mm: mm.created_at)
        ]

        agents = localData.get("agents", [])
        agent_context = next((a for a in agents if a.get("name", "").lower() == session.agent.lower()), {})

        conversation_state = conv_manager.analyze_conversation_state(messages, agent_context, session_id)

        db.close()

        return jsonify({
            "session_id": session_id,
            "agent": session.agent,
            "conversation_state": conversation_state,
            "message_count": len(messages)
        })

    except Exception as e:
        print(f"Error in conversation analysis: {str(e)}")
        return jsonify({"error": "Analysis failed"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "agents_count": len(localData.get("agents", [])),
        "openai_available": OPENAI_AVAILABLE,
        "database": "connected" if os.path.exists(DB_PATH) else "not_found",
        "conversation_manager": "active"
    })

@app.route("/")
def home():
    return jsonify({
        "status": "Backend Running",
        "timestamp": datetime.utcnow().isoformat(),
        "openai_available": OPENAI_AVAILABLE,
        "conversation_manager": "active",
        "routes": [
            "GET / - This info",
            "GET /health - Health check",
            "GET /data - View data.json",
            "GET /agents - List all agents",
            "GET /agent/<name> - Get agent details",
            "GET /conversation_analysis/<id> - Analyze conversation state",
            "POST /create_session - Create new chat session",
            "POST /initialize_session/<id> - Initialize session with AI",
            "GET /sessions - List all sessions",
            "GET /sessions/<id> - Get session details",
            "POST /sessions/<id>/messages - Add message to session",
            "POST /chat_with_ai - Chat with AI (intelligent)"
        ]
    })

if __name__ == "__main__":
    print("Starting Flask server with enhanced conversation management...")
    print(f"Database path: {DB_PATH}")
    print(f"Data.json path: {DATA_JSON_PATH}")
    print(f"Data.json exists: {os.path.exists(DATA_JSON_PATH)}")
    print(f"Agents loaded: {len(localData.get('agents', []))}")
    print(f"OpenAI client available: {OPENAI_AVAILABLE}")
    print(f"Conversation Manager: Active")

    app.run(host="0.0.0.0", port=5000, debug=True)
    
    
    
    
    
    
    
    
    
    
    
    
    