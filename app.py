from datetime import datetime
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import Settlement, db, User, Crop, Investment, ContractBlock, CropStatusUpdate
import pickle
import numpy as np

from utils import get_geotag_data
app = Flask(__name__)
app.config['SECRET_KEY'] = 'hackathon_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agri_chain.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
with open('crop_model.pkl', 'rb') as f:
    ml_model = pickle.load(f)

@app.route('/ai_advisor', methods=['GET', 'POST'])
@login_required
def ai_advisor():
    prediction = None
    if request.method == 'POST':
        # Get data from form
        data = [
            float(request.form.get('N')),
            float(request.form.get('P')),
            float(request.form.get('K')),
            float(request.form.get('temp')),
            float(request.form.get('hum')),
            float(request.form.get('ph')),
            float(request.form.get('rain'))
        ]
        
        # Predict
        prediction = ml_model.predict([data])[0]
        
    return render_template('ai_advisor.html', prediction=prediction)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')
def add_to_blockchain(data):
    last_block = ContractBlock.query.order_by(ContractBlock.id.desc()).first()
    prev_hash = last_block.hash if last_block else "0"
    new_block = ContractBlock(data=str(data), previous_hash=prev_hash)
    new_block.hash = new_block.compute_hash()
    db.session.add(new_block)
    db.session.commit()
    return new_block.hash

# --- ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        
        # Capture all new fields from the form
        new_user = User(
            username=request.form['username'],
            password=hashed_pw,
            role=request.form['role'],
            phone=request.form['phone'],
            address=request.form['address'],
            id_number=request.form['id_number']
        )
        
        db.session.add(new_user)
        db.session.commit()
        flash("Account created! Please login.")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')



# 2. CALCULATE SCORE (Investor Side)
@app.route('/crop/<int:crop_id>')
@login_required
def crop_details(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    
    # ML Prediction Logic
    features = [crop.n_content, crop.p_content, crop.k_content, crop.temp, crop.humidity, crop.ph, crop.rainfall]
    
    # Get probabilities for all crop types
    probs = ml_model.predict_proba([features])[0]
    classes = ml_model.classes_.tolist()
    
    if crop.name in classes:
        idx = classes.index(crop.name)
        confidence = round(probs[idx] * 100, 1) # Probability of THIS specific crop
    else:
        confidence = 0
        
    return render_template('crop_details.html', crop=crop, ai_score=confidence)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'farmer':
        pending_settlements = Settlement.query.join(Investment).join(Crop).filter(
            Crop.farmer_id == current_user.id, 
            Settlement.status == 'Pending Action'
        ).all()
        return render_template('farmer_dash.html', settlements=pending_settlements)
    else:
        # Investor Marketplace View
        marketplace = Crop.query.filter(Crop.sold_shares < Crop.total_shares).all()
        return render_template('investor_dash.html', marketplace=marketplace)
# --- NEW ROUTE: Manage Crops & Status Updates ---
@app.route('/my_crops')
@login_required
def my_crops():
    if current_user.role != 'farmer':
        return redirect(url_for('dashboard'))
    crops = Crop.query.filter_by(farmer_id=current_user.id).all()
    return render_template('farmer_crops.html', crops=crops)

# --- UNIFIED ROUTE: Handle both showing the form and saving the crop ---
@app.route('/new_crop', methods=['GET', 'POST'])
@login_required
def new_crop():
    if current_user.role != 'farmer':
        return redirect(url_for('dashboard'))

    # 1. GET Logic: Pre-fill data if coming from AI Advisor
    if request.method == 'GET':
        auto_data = {
            'name': request.args.get('name', ''),
            'n': request.args.get('n', ''),
            'p': request.args.get('p', ''),
            'k': request.args.get('k', ''),
            'temp': request.args.get('temp', ''),
            'hum': request.args.get('hum', ''),
            'ph': request.args.get('ph', ''),
            'rain': request.args.get('rain', '')
        }
        return render_template('farmer_new_crop.html', auto_data=auto_data)

    # 2. POST Logic: Save the crop WITH all soil data
    if request.method == 'POST':
        # Get the image if provided
        image_url = 'uploads/default_crop.jpg'
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f'uploads/{filename}'

        # Create the new crop object with all 7 ML features
        new_crop = Crop(
            name=request.form.get('name', '').lower().strip(),
            total_shares=int(request.form.get('shares', 0)),
            # Use 'funding_goal' if your model uses it, otherwise 0
            funding_goal=float(request.form.get('goal', 0)), 
            farmer_id=current_user.id,
            image_url=image_url,
            # CRITICAL: Capture the soil data from the form
            n_content=float(request.form.get('n', 0)),
            p_content=float(request.form.get('p', 0)),
            k_content=float(request.form.get('k', 0)),
            temp=float(request.form.get('temp', 0)),
            humidity=float(request.form.get('hum', 0)),
            ph=float(request.form.get('ph', 0)),
            rainfall=float(request.form.get('rain', 0))
        )
        
        db.session.add(new_crop)
        db.session.commit()
        
        flash(f"Successfully listed {new_crop.name} with AI verification data!")
        return redirect(url_for('my_crops'))
@app.route('/my_investments')
@login_required
def my_investments():
    # Security check: Only investors should access this
    if current_user.role != 'investor':
        flash("Unauthorized access.")
        return redirect(url_for('dashboard'))
        
    investments = Investment.query.filter_by(investor_id=current_user.id, status='Active').all()
    return render_template('my_investments.html', investments=investments)
@app.route('/resolve_settlement/<int:settlement_id>', methods=['POST'])
@login_required
def resolve_settlement(settlement_id):
    if current_user.role != 'farmer':
        return redirect(url_for('dashboard'))

    settlement = Settlement.query.get_or_404(settlement_id)
    
    # 1. Save the Receipt Image
    if 'receipt_image' in request.files:
        file = request.files['receipt_image']
        if file.filename != '':
            filename = secure_filename(file.filename)
            receipts_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'receipts')
            os.makedirs(receipts_dir, exist_ok=True)
            
            path = os.path.join(receipts_dir, filename)
            file.save(path)
            settlement.proof_image = f'uploads/receipts/{filename}'
    
    # 2. Update Statuses to move it to History
    settlement.status = 'Completed'
    settlement.investment.status = 'History' # This hides it from "My Portfolio"
    
    db.session.commit()
    flash("Fulfillment proof uploaded. Contract moved to Investor History.")
    return redirect(url_for('dashboard'))
@app.route('/track_crop/<int:crop_id>')
@login_required
def track_crop(crop_id):
    # Fetch the crop and its updates
    crop = Crop.query.get_or_404(crop_id)
    # Fetch the specific investment for this user to show their contract hash
    investment = Investment.query.filter_by(investor_id=current_user.id, crop_id=crop_id).first()
    
    return render_template('track_crop.html', crop=crop, investment=investment)
@app.route('/history') # <--- This string must match the link
@login_required
def history():
    if current_user.role != 'investor':
        return redirect(url_for('dashboard'))
    
    # Ensure you are querying the 'History' status
    history = Investment.query.filter_by(investor_id=current_user.id, status='History').all()
    return render_template('history.html', history=history)


@app.route('/invest/<int:crop_id>', methods=['POST'])
@login_required
def invest(crop_id):
    crop = Crop.query.get(crop_id)
    
    # Get the custom quantity from the form
    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        flash("Invalid quantity.")
        return redirect(url_for('dashboard'))

    # Check availability
    available_shares = crop.total_shares - crop.sold_shares
    if quantity > available_shares:
        flash(f"Only {available_shares} shares available.")
        return redirect(url_for('dashboard'))

    # Logical Workflow
    crop.sold_shares += quantity
    
    # Update Crop Status to 'Funded' if goal is reached
    if crop.sold_shares == crop.total_shares:
        crop.status = 'Funded'

    # Record the batch investment on the Blockchain
    contract_data = {
        "investor": current_user.username,
        "crop": crop.name,
        "shares_purchased": quantity,
        "timestamp": str(datetime.utcnow())
    }
    tx_hash = add_to_blockchain(contract_data)

    # Save to Database
    new_inv = Investment(
        investor_id=current_user.id, 
        crop_id=crop.id, 
        blockchain_hash=tx_hash
        # You might want to add a 'quantity' column to your Investment model too
    )
    
    db.session.add(new_inv)
    db.session.commit()
    
    flash(f"Successfully invested in {quantity} shares!")
    return redirect(url_for('dashboard'))

@app.route('/update_progress/<int:crop_id>', methods=['POST'])
@login_required
def update_progress(crop_id):
    if current_user.role != 'farmer':
        return redirect(url_for('dashboard'))

    crop = Crop.query.get_or_404(crop_id)
    status_text = request.form.get('status_text')
    
    # 1. Handle Image Upload
    file = request.files['status_image']
    filename = secure_filename(file.filename)
    
    # Ensure the updates directory exists
    updates_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'updates')
    os.makedirs(updates_dir, exist_ok=True)
    
    # Save the file
    file.save(os.path.join(updates_dir, filename))
    file_path = f'uploads/updates/{filename}'

    # 2. Update Main Crop Status
    crop.status = status_text
    
    # 3. Create Status Record with Image
    lat, lng = get_geotag_data(file_path)
    
    # 3. Create Record
    update = CropStatusUpdate(
        crop_id=crop.id, 
        status_text=status_text, 
        image_url=f'uploads/updates/{filename}',
        latitude=lat,  # Will be None if not found
        longitude=lng  # Will be None if not found
    )
    # 4. Log to Blockchain with Image Proof
    add_to_blockchain({
        "event": "Progress Update", 
        "status": status_text, 
        "crop": crop.name,
        "proof_file": filename # Adds transparency to the ledger
    })
    
    db.session.add(update)
    db.session.commit()
    if "harvested" in status_text.lower():
        crop.status = "Harvested"
    
    # Logic: If the farmer marks "Failed" or "Destroyed"
    if "failed" in status_text.lower():
        crop.status = "Failed - Refund Triggered"
        # In a real app, you would run: refund_investors(crop_id)
        
    db.session.commit()
    return redirect(url_for('my_crops'))
@app.route('/settle_contract/<int:inv_id>/<action>', methods=['GET', 'POST'])
@login_required
def settle_contract(inv_id, action):
    investment = Investment.query.get_or_404(inv_id)
    
    if request.method == 'POST':
        if action == 'interest':
            # Combine bank fields
            data = [
                f"Bank: {request.form.get('bank_name')}",
                f"Holder: {request.form.get('holder_name')}",
                f"A/C: {request.form.get('acc_number')}",
                f"IFSC: {request.form.get('ifsc')}"
            ]
        else:
            # Combine shipping fields
            data = [
                f"Name: {request.form.get('ship_name')}",
                f"Addr: {request.form.get('ship_address')}",
                f"City: {request.form.get('ship_city')}",
                f"Phone: {request.form.get('ship_phone')}"
            ]
        
        # Store as a multi-line string
        secure_details = "\n".join(data)
        
        new_settlement = Settlement(
            investment_id=investment.id,
            settlement_type=action,
            details=secure_details
        )
        investment.status = 'History'
        db.session.add(new_settlement)
        db.session.commit()
        
        flash("Settlement requested! The Farmer can now see your organized details.")
        return redirect(url_for('my_investments'))

    return render_template('settlement_form.html', investment=investment, action=action)
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)