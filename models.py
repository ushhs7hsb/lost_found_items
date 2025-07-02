from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Relationships
    items = db.relationship('Item', backref='owner', lazy=True, foreign_keys='[Item.user_id]')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    claimed_items = db.relationship('Item', backref='claimer', lazy=True, foreign_keys='[Item.claimed_by]')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    item_type = db.Column(db.String(10), nullable=False)  # 'lost' or 'found'
    questions = db.Column(db.JSON, nullable=False)
    answers = db.Column(db.JSON, nullable=False)
    contact_info = db.Column(db.String(100), nullable=False)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    allowed_user_id = db.Column(db.Integer)
    claimed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Other fields
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    contact_shared = db.Column(db.Boolean, default=False)
    image_filename = db.Column(db.String(100))
    pending_answers = db.Column(db.JSON)
    claimed = db.Column(db.Boolean, default=False)
    claimed_at = db.Column(db.DateTime)
    
    # Relationships
    messages = db.relationship('Message', backref='item', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())