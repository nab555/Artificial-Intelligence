# stock_price_prediction.py
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd

# Download stock data
data = yf.download("AAPL", start="2022-01-01", end="2023-12-31")
data['MA_20'] = data['Close'].rolling(window=20).mean()
data['MA_50'] = data['Close'].rolling(window=50).mean()

# Plot
plt.figure(figsize=(10,5))
plt.plot(data['Close'], label='Close Price', color='blue')
plt.plot(data['MA_20'], label='20-Day MA', color='red')
plt.plot(data['MA_50'], label='50-Day MA', color='green')
plt.title('AAPL Stock Price Prediction using Moving Average')
plt.legend()
plt.show()
