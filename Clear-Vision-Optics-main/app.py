import json
import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ====== CONTEXT PROCESSOR - Makes admin status available in ALL templates ======
@app.context_processor
def inject_admin_status():
    return dict(is_admin=session.get('admin_logged_in', False))

# ====== ⚙️ CONFIGURATION - SET YOUR PASSWORD HERE ======
# ⚠️ CHANGE THIS TO YOUR DESIRED ADMIN PASSWORD (NO ENV VARIABLES NEEDED!)
ADMIN_PASSWORD = "ClearVision001"  # ←←← SET YOUR PASSWORD HERE

# File paths
PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)

# ====== UTILITY FUNCTIONS ======
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        return []
    try:
        with open(PRODUCTS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading products: {e}")
        return []

def save_products(products):
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(products, f, indent=2)

def get_categories():
    products = load_products()
    return sorted(set(p.get('category', 'uncategorized').lower() for p in products))

# ====== ROUTES ======
@app.route('/')
def home():
    products = load_products()
    featured = [p for p in products if p.get('is_featured', False)][:4]
    return render_template('index.html', 
                         featured_products=featured,
                         testimonials=[
                             {"name": "Jane O.", "text": "After years of headaches from screen use, the blue light glasses from Clear Vision changed everything."},
                             {"name": "David M.", "text": "As a teacher who spends all day reading, my progressive lenses are life-changing."},
                             {"name": "Amina K.", "text": "My son needed his first pair of glasses. The optician was so patient with him!"}
                         ])

@app.route('/products')
def products():
    category = request.args.get('category', '').lower()
    search = request.args.get('search', '').lower()
    products_list = load_products()
    
    if category and category != 'all':
        products_list = [p for p in products_list if p.get('category', '').lower() == category]
    if search:
        products_list = [p for p in products_list if search in p.get('name', '').lower() or 
                        search in p.get('description', '').lower()]
    
    return render_template('products.html', 
                         products=products_list,
                         categories=get_categories(),
                         selected_category=category,
                         search_query=search)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    product = request.args.get('product', '')
    return render_template('contact.html', requested_product=product)

# ====== ADMIN ROUTES ======
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('✅ Welcome to Clear Vision Admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('❌ Incorrect password. Try again.', 'error')
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    products = load_products()
    # Pre-calculate stats to avoid template errors
    featured_count = sum(1 for p in products if p.get('is_featured'))
    category_count = len(set(p.get('category', 'uncategorized').lower() for p in products))
    
    return render_template('admin/dashboard.html', 
                         products=products,
                         total_count=len(products),
                         featured_count=featured_count,
                         category_count=category_count)

@app.route('/admin/add', methods=['GET', 'POST'])
def admin_add_product():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        products = load_products()
        
        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Generate unique filename to avoid conflicts
                ext = file.filename.rsplit('.', 1)[1].lower()
                image_filename = f"product_{len(products) + 1}_{secrets.token_hex(4)}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, image_filename))
        
        # Parse features (handle both comma and newline separators)
        features_text = request.form.get('features', '')
        features = []
        if features_text:
            # Split by newline first, then by comma if needed
            lines = features_text.split('\n')
            for line in lines:
                if line.strip():
                    features.append(line.strip())
            if not features:  # Try comma separation
                features = [f.strip() for f in features_text.split(',') if f.strip()]
        
        new_product = {
            "id": max([p['id'] for p in products], default=0) + 1,
            "name": request.form['name'].strip(),
            "description": request.form['description'].strip(),
            "price": float(request.form['price']),
            "image": image_filename,
            "category": request.form['category'].lower().strip(),
            "features": features,
            "is_featured": 'is_featured' in request.form
        }
        
        products.append(new_product)
        save_products(products)
        flash(f'✅ "{new_product["name"]}" added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/add_product.html', categories=get_categories())

@app.route('/admin/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    products = load_products()
    original_count = len(products)
    products = [p for p in products if p['id'] != product_id]
    
    # Delete associated image file
    deleted_product = [p for p in load_products() if p['id'] == product_id]
    if deleted_product and deleted_product[0].get('image'):
        image_path = os.path.join(UPLOAD_FOLDER, deleted_product[0]['image'])
        if os.path.exists(image_path):
            os.remove(image_path)
    
    save_products(products)
    
    if len(products) < original_count:
        flash('✅ Product deleted successfully!', 'success')
    else:
        flash('⚠️ Product not found', 'warning')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('👋 You\'ve been logged out', 'info')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)