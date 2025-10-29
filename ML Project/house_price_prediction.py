# house_price_prediction.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

# Sample dataset
data = {
    'area': [1000, 1500, 2000, 2500, 3000],
    'bedrooms': [2, 3, 3, 4, 4],
    'age': [10, 5, 8, 4, 2],
    'price': [100000, 150000, 200000, 250000, 300000]
}

df = pd.DataFrame(data)

# Features and target
X = df[['area', 'bedrooms', 'age']]
y = df['price']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Model
model = LinearRegression()
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

# Evaluate
mae = mean_absolute_error(y_test, y_pred)
print("Mean Absolute Error:", mae)
print("Predicted Prices:", y_pred)
