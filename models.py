import hashlib
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20))      # New Field
    address = db.Column(db.Text)          # New Field
    id_number = db.Column(db.String(50))  # New Field
    trust_score = db.Column(db.Integer, default=95) # Default high trust

class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_shares = db.Column(db.Integer)
    sold_shares = db.Column(db.Integer, default=0)
    funding_goal = db.Column(db.Float)
    image_url = db.Column(db.String(200))
    status = db.Column(db.String(50), default="Open") # Open, Funded, Harvested
    updates = db.relationship('CropStatusUpdate', backref='crop', lazy=True)
    # NEW FIELDS FOR ML
    n_content = db.Column(db.Float, default=0.0)
    p_content = db.Column(db.Float, default=0.0)
    k_content = db.Column(db.Float, default=0.0)
    temp = db.Column(db.Float, default=0.0)
    humidity = db.Column(db.Float, default=0.0)
    ph = db.Column(db.Float, default=0.0)
    rainfall = db.Column(db.Float, default=0.0)
    image_url = db.Column(db.String(200))
    funds_released = db.Column(db.Float, default=0.0)
    current_milestone = db.Column(db.Integer, default=1)

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    status = db.Column(db.String(50), default="Active")
    blockchain_hash = db.Column(db.String(128))
    crop = db.relationship('Crop', backref='investments')

class CropStatusUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    status_text = db.Column(db.String(200))
    image_url = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class ContractBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    data = db.Column(db.Text)
    previous_hash = db.Column(db.String(128))
    hash = db.Column(db.String(128))

    def compute_hash(self):
        block_string = json.dumps({"data": self.data, "prev": self.previous_hash}, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'))
    settlement_type = db.Column(db.String(50)) # 'interest' or 'physical_crop'
    details = db.Column(db.Text) # Stores Bank/UPI details OR Shipping Address
    status = db.Column(db.String(50), default="Pending Action")
    proof_image = db.Column(db.String(200)) # To store Farmer's payment/shipping receipt
    resolved_at = db.Column(db.DateTime)
    # Creates a 1-to-1 virtual link back to the investment
    investment = db.relationship('Investment', backref=db.backref('settlement', uselist=False))