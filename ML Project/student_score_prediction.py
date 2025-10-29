# student_score_prediction.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

# Create dataset
data = {'Hours': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'Scores': [25, 30, 45, 50, 60, 70, 75, 80, 85, 90]}
df = pd.DataFrame(data)

# Split
X = df[['Hours']]
y = df['Scores']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train
model = LinearRegression()
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

# Plot
plt.scatter(df['Hours'], df['Scores'], color='blue')
plt.plot(df['Hours'], model.predict(df[['Hours']]), color='red')
plt.xlabel("Study Hours")
plt.ylabel("Score")
plt.title("Study Hours vs Exam Score")
plt.show()

print("Predicted Scores:", y_pred)
