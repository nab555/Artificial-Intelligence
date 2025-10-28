# iris_classifier.py
# Simple Machine Learning project using scikit-learn

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

# Load sample dataset
X, y = load_iris(return_X_y=True)

# Split into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = LogisticRegression(max_iter=200)
model.fit(X_train, y_train)

# Make predictions
pred = model.predict(X_test)

# Evaluate
print("Accuracy:", accuracy_score(y_test, pred))
