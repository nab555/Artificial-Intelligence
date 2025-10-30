# loan_approval_prediction.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# Load dataset
url = "https://raw.githubusercontent.com/dphi-official/Datasets/master/loan_data.csv"
df = pd.read_csv(url)

# Handle missing values
df.fillna(method='ffill', inplace=True)

# Encode categorical columns
le = LabelEncoder()
for col in ['Gender', 'Married', 'Education', 'Self_Employed', 'Property_Area']:
    df[col] = le.fit_transform(df[col])

# Features and target
X = df.drop(['Loan_Status', 'Loan_ID'], axis=1)
y = le.fit_transform(df['Loan_Status'])

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

# Evaluate
print("Accuracy:", accuracy_score(y_test, y_pred))
