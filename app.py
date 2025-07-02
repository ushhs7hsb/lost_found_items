from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Item, Message
from datetime import datetime
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lost_and_found.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
@login_required
def index():
    items = Item.query.order_by(Item.created_at.desc()).all()
    return render_template('index.html', items=items)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        return 'Invalid username or password'
    
    return render_template('login.html', next=request.args.get('next'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            return 'Username already exists!'
        if User.query.filter_by(email=email).first():
            return 'Email already registered!'
        
        # Admin creation logic
        is_admin = False
        if username == 'admin' and not User.query.filter_by(is_admin=True).first():
            is_admin = True
        
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))
    
    return render_template('signup.html', next=request.args.get('next'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_items = Item.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', items=user_items)

@app.route('/post', methods=['GET', 'POST'])
@login_required
def post_item():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        item_type = request.form['item_type']
        category = request.form['category']
        contact_info = request.form['contact_info']
        questions = request.form.getlist('questions[]')

        answers = []
        if item_type == 'lost':
            answers = request.form.getlist('answers[]')

        image_file = request.files.get('image')
        image_filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            image_filename = filename

        item = Item(
            title=title,
            description=description,
            item_type=item_type,
            category=category,
            contact_info=contact_info,
            questions=questions,
            answers=answers,
            image_filename=image_filename,
            user_id=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        flash('Item posted successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('post_item.html')

@app.route('/item/<int:item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        if 'answers[]' in request.form:
            user_answers = request.form.getlist('answers[]')
            item.pending_answers = user_answers
            item.allowed_user_id = current_user.id
            db.session.commit()
            return jsonify({'success': True, 'message': 'Answers submitted! The found user will review them.'})
        
        if 'allow_contact' in request.form:
            if request.form['allow_contact'] == 'true':
                item.contact_shared = True
                db.session.commit()
                return jsonify({'contact': item.contact_info})
            else:
                item.pending_answers = None
                item.allowed_user_id = None
                db.session.commit()
                return jsonify({'message': 'Contact sharing denied.'})
    
    show_contact = item.contact_shared and current_user.id == item.allowed_user_id
    return render_template('item_detail.html', item=item, show_contact=show_contact)

@app.route('/claim_item/<int:item_id>', methods=['POST'])
@login_required
def claim_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    if not item.contact_shared:
        return jsonify({'success': False, 'message': 'Contact not shared yet'}), 400
    
    if current_user.id != item.allowed_user_id:
        return jsonify({'success': False, 'message': 'Not authorized to claim this item'}), 403
    
    if item.claimed:
        return jsonify({'success': False, 'message': 'Item already claimed'}), 400
    
    item.claimed = True
    item.claimed_by = current_user.id
    item.claimed_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Item claimed successfully'})

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    receiver_id = request.form.get('receiver_id')
    item_id = request.form.get('item_id')
    content = request.form.get('content')

    if not receiver_id or not item_id or not content:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    item = Item.query.get_or_404(item_id)
    if receiver_id != str(item.user_id) and receiver_id != str(item.allowed_user_id):
        return jsonify({'success': False, 'message': 'Invalid receiver'}), 400

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        item_id=item_id,
        content=content
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Message sent successfully'})

@app.route('/messages/<int:item_id>')
@login_required
def view_messages(item_id):
    item = Item.query.get_or_404(item_id)
    
    if current_user.id != item.user_id and current_user.id != item.allowed_user_id:
        return "You are not authorized to view these messages.", 403
    
    messages = Message.query.filter_by(item_id=item_id).order_by(Message.timestamp.asc()).all()
    return render_template('messages.html', item=item, messages=messages)

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return "Unauthorized", 403
    
    items = Item.query.order_by(Item.created_at.desc()).all()
    users = User.query.order_by(User.id).all()
    return render_template('admin_dashboard.html', items=items, users=users)

@app.route('/admin/delete_item/<int:item_id>', methods=['POST'])
@login_required
def admin_delete_item(item_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    item = Item.query.get_or_404(item_id)
    
    # Delete associated messages
    Message.query.filter_by(item_id=item_id).delete()
    
    # Delete image if exists
    if item.image_filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item.image_filename))
        except Exception as e:
            app.logger.error(f"Error deleting image: {str(e)}")
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Item deleted successfully'})

@app.route('/admin/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_item(item_id):
    if not current_user.is_admin:
        return "Unauthorized", 403
    
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        try:
            # Update basic fields
            item.title = request.form.get('title', item.title)
            item.description = request.form.get('description', item.description)
            item.item_type = request.form.get('item_type', item.item_type)
            item.category = request.form.get('category', item.category)
            item.contact_info = request.form.get('contact_info', item.contact_info)
            
            # Handle questions and answers
            questions = request.form.getlist('questions[]')
            answers = request.form.getlist('answers[]')
            
            # Validate Q&A pairs
            if item.item_type == 'lost' and (len(questions) != len(answers) or len(questions) == 0):
                flash('Invalid security questions/answers configuration', 'danger')
                return redirect(url_for('admin_edit_item', item_id=item_id))
            
            item.questions = questions
            item.answers = answers if item.item_type == 'lost' else []

            # Handle image update
            image_file = request.files.get('image')
            if image_file and image_file.filename:
                if allowed_file(image_file.filename):
                    # Remove old image
                    if item.image_filename:
                        try:
                            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item.image_filename))
                        except Exception as e:
                            app.logger.error(f"Error removing old image: {str(e)}")
                    
                    # Save new image
                    filename = secure_filename(image_file.filename)
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image_file.save(image_path)
                    item.image_filename = filename
                else:
                    flash('Invalid file type for image', 'danger')
                    return redirect(url_for('admin_edit_item', item_id=item_id))

            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating item: {str(e)}")
            flash('Error updating item', 'danger')
            return redirect(url_for('admin_edit_item', item_id=item_id))
    
    return render_template('admin_edit_item.html', item=item)

@app.route('/admin/toggle_claim/<int:item_id>', methods=['POST'])
@login_required
def admin_toggle_claim(item_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        item = Item.query.get_or_404(item_id)
        item.claimed = not item.claimed
        if item.claimed:
            item.claimed_at = datetime.utcnow()
            item.claimed_by = current_user.id
        else:
            item.claimed_at = None
            item.claimed_by = None
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Claim status updated',
            'claimed': item.claimed
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error toggling claim status: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating claim status'}), 500


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)