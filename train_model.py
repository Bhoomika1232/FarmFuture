import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import pickle

# 1. Load the data
# Ensure 'Crop_recommendation.csv' is in the same folder as this script
df = pd.read_csv('Crop_recommendation.csv')

# 2. Separate Features (X) and Target (y)
X = df[['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']]
y = df['label']

# 3. Split the data
# test_size=0.2 means 80% for training and 20% for testing
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Initialize and Train the Model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 5. Save the trained model to a 'pickle' file
with open('crop_model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("Success: Model trained and saved as 'crop_model.pkl'")