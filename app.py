from flask import Flask, render_template, redirect, url_for, request, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_migrate import Migrate
from functools import wraps
import os
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('book_id', db.Integer, db.ForeignKey('book.id'))
)

# ================== Models ==================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150))
    class_name = db.Column(db.String(10))
    division = db.Column(db.String(10))
    roll_no = db.Column(db.String(10))
    favorites = db.relationship('Book', secondary=favorites, backref='favorited_by')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    book = db.relationship('Book', backref='reviews')
    user = db.relationship('User', backref='reviews')

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_borrowed = db.Column(db.Boolean, default=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    returned = db.Column(db.Boolean, default=False)
    returned_at = db.Column(db.DateTime, nullable=True)

    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_books')
    borrower = db.relationship('User', foreign_keys=[borrower_id], backref='borrowed_books')

# ================== Auth ==================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

# ================== Routes ==================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']

    # Current books
    owned_books = Book.query.filter_by(owner_id=user_id, is_borrowed=False).all()
    borrowed_books = Book.query.filter_by(borrower_id=user_id, is_borrowed=True).all()
    user_has_borrowed = bool(borrowed_books)

    now = datetime.utcnow()
    has_overdue = any(book.due_date and book.due_date < now for book in borrowed_books)

    # History
    borrowed_history = Book.query.filter_by(borrower_id=user_id, returned=True).all()
    lent_history = Book.query.filter_by(owner_id=user_id, returned=True).all()

    return render_template('dashboard.html',
        owned_books=owned_books,
        borrowed_books=borrowed_books,
        user_has_borrowed=user_has_borrowed,
        has_overdue=has_overdue,
        borrowed_history=borrowed_history,
        lent_history=lent_history,
        current_time=now
    )

@app.route('/history')
@login_required
def history():
    user_id = session['user_id']

    # Books the user borrowed and returned
    borrowed_history = Book.query.filter_by(borrower_id=user_id, returned=True).order_by(Book.returned_at.desc()).all()

    # Books the user owns and have been returned by others
    lent_history = Book.query.filter_by(owner_id=user_id, returned=True).order_by(Book.returned_at.desc()).all()

    return render_template('history.html',
                           borrowed_history=borrowed_history,
                           lent_history=lent_history)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/toggle_favorite/<int:book_id>', methods=['POST'])
@login_required
def toggle_favorite(book_id):
    book = Book.query.get_or_404(book_id)
    user = User.query.get(session['user_id'])

    if book in user.favorites:
        user.favorites.remove(book)
        flash("💔 Removed from favorites.")
    else:
        user.favorites.append(book)
        flash("❤️ Added to favorites!")

    db.session.commit()
    return redirect(request.referrer or url_for('available_books'))

@app.route('/review/<int:book_id>', methods=['GET', 'POST'])
@login_required
def review_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment']

        review = Review(book_id=book.id, user_id=session['user_id'], rating=rating, comment=comment)
        db.session.add(review)
        db.session.commit()
        flash("✅ Thanks for your review!")
        return redirect(url_for('history'))

    return render_template('review.html', book=book)

@app.route('/recommend/<int:book_id>', methods=['POST'])
@login_required
def recommend_book(book_id):
    book = Book.query.get_or_404(book_id)
    friend_email = request.form.get('friend_email')

    if not friend_email:
        flash("Please enter a valid email address.")
        return redirect(url_for('available_books'))

    message = f"📚 {session['name']} recommends you check out this book: '{book.title}' by {book.author}!"
    send_email(friend_email, f"Book Recommendation: {book.title}", message)

    flash(f"✅ Book recommended to {friend_email}!")
    return redirect(url_for('available_books'))

@app.route('/qr/<int:book_id>')
@login_required
def show_qr_code(book_id):
    book = Book.query.get_or_404(book_id)

    if book.borrower_id != session['user_id']:
        flash("You are not allowed to view the QR code for this book.")
        return redirect(url_for('dashboard'))

    borrower = User.query.get(session['user_id'])
    owner = book.owner

    pickup_instructions = (
        f"Book: {book.title}\n"
        f"Owner: {owner.name}\n"
        f"Class: {owner.class_name}-{owner.division}\n"
        f"Show this to collect the book during lunch break!"
    )

    qr_img = qrcode.make(pickup_instructions)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    import base64
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return render_template('qr_code.html', book=book, qr_base64=qr_base64)

@app.route('/qr_download/<int:book_id>')
@login_required
def download_qr_code(book_id):
    book = Book.query.get_or_404(book_id)

    if book.borrower_id != session['user_id']:
        flash("You are not allowed to download the QR code for this book.")
        return redirect(url_for('dashboard'))

    borrower = User.query.get(session['user_id'])
    owner = book.owner

    pickup_info = (
        f"Book: {book.title}\n"
        f"Owner: {owner.name}\n"
        f"Class: {owner.class_name}-{owner.division}\n"
        f"Pickup: Lunch break in their classroom."
    )

    qr = qrcode.make(pickup_info)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    buffer.seek(0)

    filename = f"{book.title}_qr.png"
    return send_file(buffer, mimetype='image/png', as_attachment=True, download_name=filename)

@app.route('/favorites')
@login_required
def view_favorites():
    user = User.query.get(session['user_id'])
    return render_template('favorites.html', favorites=user.favorites)

@app.route('/delete_book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.owner_id != session['user_id']:
        flash("You are not allowed to delete this book.")
        return redirect(url_for('dashboard'))
    db.session.delete(book)
    db.session.commit()
    flash("📕 Book deleted successfully.")
    return redirect(url_for('dashboard'))

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')
    books = Book.query.filter(
        Book.title.ilike(f'%{query}%') | Book.author.ilike(f'%{query}%')
    ).all() if query else []
    return render_template('search_results.html', books=books, query=query)

@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        description = request.form.get('description')
        user_id = session['user_id']
        cover_file = request.files['cover_image']

        cover_filename = None
        if cover_file:
            cover_filename = f"{title}_{datetime.utcnow().timestamp()}.png"
            cover_path = os.path.join('static', 'uploads', cover_filename)
            os.makedirs(os.path.dirname(cover_path), exist_ok=True)
            cover_file.save(cover_path)

        new_book = Book(
            title=title,
            author=author,
            description=description,
            owner_id=user_id,
            cover_image=cover_filename
        )
        db.session.add(new_book)
        db.session.commit()

        flash("Book added successfully!")
        return redirect(url_for('dashboard'))
    return render_template('add_book.html')

@app.route('/borrow_book/<int:book_id>', methods=['POST'])
@login_required
def borrow_book(book_id):
    book = Book.query.get_or_404(book_id)
    user_id = session['user_id']

    if book.is_borrowed:
        flash("⚠️ Book is already borrowed.")
        return redirect(url_for('dashboard'))

    existing = Book.query.filter_by(borrower_id=user_id, is_borrowed=True).first()
    if existing:
        flash("⚠️ You can only borrow one book at a time.")
        return redirect(url_for('dashboard'))

    book.borrower_id = user_id
    book.is_borrowed = True
    book.due_date = datetime.utcnow() + timedelta(days=7)
    db.session.commit()

    borrower = User.query.get(user_id)
    owner = book.owner

    pickup_instructions = (
        f"Book: {book.title}\n"
        f"Owner: {owner.name}\n"
        f"Class: {owner.class_name}-{owner.division}\n"
        f"Show this to collect the book during lunch break!"
    )

    qr_img = qrcode.make(pickup_instructions)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    message = (
        f"{borrower.name} (Class {borrower.class_name}-{borrower.division}, Roll No. {borrower.roll_no}) "
        f"has borrowed your book '{book.title}'.\n\nPlease bring it to your class during lunch break."
    )

    try:
        msg = Message(
            "📚 Your book was borrowed!",
            recipients=[owner.gmail],
            body=message,
            sender=app.config['MAIL_USERNAME']
        )
        msg.attach(f"{book.title}_QR.png", "image/png", buffer.read())
        mail.send(msg)
    except Exception as e:
        print("Failed to send email with QR:", e)

    flash("✅ Book borrowed! Please go to the owner's class during lunch break.")
    return redirect(url_for('show_qr_code', book_id=book.id))

@app.route('/borrow/<int:book_id>')
@login_required
def borrow_get_debug(book_id):
    return "Borrow route should only be POST."

@app.route('/return/<int:book_id>', methods=['POST'])
@login_required
def return_book(book_id):
    book = Book.query.get_or_404(book_id)
    user_id = session['user_id']

    if book.borrower_id != user_id:
        flash('You are not allowed to return this book.')
        return redirect(url_for('dashboard'))

    book.is_borrowed = False
    book.due_date = None
    book.returned = True
    book.returned_at = datetime.utcnow()
    # borrower_id is kept for history purposes ✅

    db.session.commit()

    if book.owner:
        send_email(book.owner.gmail, "📤 Your book was returned", f"{book.title} was returned by {session['name']}")

    flash("✅ Book returned.")
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        gmail = request.form['gmail']
        password = request.form['password']
        class_name = request.form['class_name']
        division = request.form['division']
        roll_no = request.form['roll_no']

        if User.query.filter_by(gmail=gmail).first():
            flash('Email already registered.')
            return redirect(url_for('register'))

        user = User(gmail=gmail, name=name, class_name=class_name, division=division, roll_no=roll_no)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        flash('Registration successful. Welcome!')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        gmail = request.form['gmail']
        password = request.form['password']
        user = User.query.filter_by(gmail=gmail).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['name'] = user.name
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/available_books')
@login_required
def available_books():
    user_id = session['user_id']
    books = Book.query.filter(
        Book.is_borrowed == False,
        Book.owner_id != user_id
    ).all()

    # Only count books that are still borrowed and not returned
    user_has_borrowed = Book.query.filter_by(borrower_id=user_id, is_borrowed=True).first() is not None

    user = User.query.get(user_id)
    favorite_books = {book.id for book in user.favorites}

    return render_template('available_books.html',
        books=books,
        user_has_borrowed=user_has_borrowed,
        favorites=favorite_books
    )

# ================== Email Helper ==================
def send_email(to, subject, body):
    try:
        msg = Message(subject, recipients=[to], body=body, sender=app.config['MAIL_USERNAME'])
        mail.send(msg)
    except Exception as e:
        print("Email failed:", e)

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Book': Book
    }

# ================== CLI Commands ==================
@app.cli.command('send_due_reminders')
def send_due_reminders():
    tomorrow = datetime.utcnow() + timedelta(days=1)
    books_due = Book.query.filter(
        Book.due_date != None,
        Book.due_date.between(datetime.utcnow(), tomorrow)
    ).all()

    for book in books_due:
        borrower = book.borrower
        if borrower and borrower.gmail:
            send_email(
                borrower.gmail,
                "📅 Reminder: Book due tomorrow!",
                f"Please return '{book.title}' to {book.owner.name} "
                f"(Class: {book.owner.class_name}, Division: {book.owner.division}) during lunch break."
            )

@app.cli.command('send_overdue_alerts')
def send_overdue_alerts():
    now = datetime.utcnow()
    overdue_books = Book.query.filter(
        Book.due_date != None,
        Book.due_date < now
    ).all()

    for book in overdue_books:
        if book.borrower and book.owner:
            send_email(
                book.borrower.gmail,
                "⏰ Overdue Book Alert!",
                f"You are late returning '{book.title}'! Please return it to {book.owner.name} immediately."
            )
            send_email(
                book.owner.gmail,
                "⏰ Your Book is Overdue!",
                f"'{book.title}' is overdue. Borrower: {book.borrower.name} ({book.borrower.class_name}-{book.borrower.division})."
            )

# ================== Run ==================
if __name__ == '__main__':
    app.run(debug=True)
