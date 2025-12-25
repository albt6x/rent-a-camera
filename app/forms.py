from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    BooleanField,
    TextAreaField,
    DecimalField,
    IntegerField,
    SelectField,
)
from wtforms.fields import DateField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    ValidationError,
    Length,
    Regexp,
)
from flask_login import current_user
from datetime import date
from app.models import User, Category, Item
from flask import current_app
import os

# ------------------------------------------------------------------
# Helper validators
# ------------------------------------------------------------------
def FileSize(max_size_bytes=None):
    """
    Factory for a WTForms validator that ensures uploaded file is <= max_size_bytes.
    """
    def _file_size(form, field):
        f = getattr(field, "data", None)
        if not f:
            return

        try:
            if max_size_bytes is None:
                limit = int(current_app.config.get("MAX_UPLOAD_IMAGE_BYTES", 5 * 1024 * 1024))
            else:
                limit = int(max_size_bytes)
        except Exception:
            limit = 5 * 1024 * 1024

        try:
            size = None
            stream = getattr(f, "stream", None)
            if stream and hasattr(stream, "seek") and hasattr(stream, "tell"):
                cur = stream.tell()
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(cur)
            else:
                size = getattr(f, "content_length", None)

            if size is None:
                return

            if size > limit:
                mb = limit / (1024 * 1024)
                raise ValidationError(f"File terlalu besar. Maksimum {mb:.1f} MB.")
        except ValidationError:
            raise
        except Exception:
            return

    return _file_size


# ------------------------------------------------------------------
# 1. REGISTRATION FORM
# ------------------------------------------------------------------
class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=2, max=20, message="Username must be between 2 and 20 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(message="Email is required."), Email(message="Please enter a valid email address.")],
    )
    
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, max=72, message="Password minimal 8 karakter."),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[\W_]).+$",
                message="Minimal 8 karakter, 1 Huruf Besar, 1 Angka, 1 Simbol.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(message="Please confirm your password."), EqualTo("password", message="Password tidak cocok.")],
    )
    submit = SubmitField("Create Account")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("That username is already taken. Please choose another.")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("That email is already registered. Please use a different email.")


# ------------------------------------------------------------------
# 2. LOGIN FORM
# ------------------------------------------------------------------
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(message="Email is required."), Email(message="Please enter a valid email address.")])
    password = PasswordField("Password", validators=[DataRequired(message="Password is required.")])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Login")


# ------------------------------------------------------------------
# 3. UPDATE ACCOUNT FORM
# ------------------------------------------------------------------
class UpdateAccountForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=2, max=20, message="Username must be between 2 and 20 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(message="Email is required."), Email(message="Please enter a valid email address.")],
    )

    phone = StringField(
        "WhatsApp Number (62...)",
        validators=[
            DataRequired(message="WhatsApp number is required."),
            Length(min=10, max=15, message="Nomor HP harus antara 10-15 digit."),
            Regexp(r'^[0-9]+$', message="Hanya boleh angka.")
        ],
    )

    picture = FileField(
        "Change Profile Picture",
        validators=[
            FileAllowed(["jpg", "jpeg", "png", "webp", "gif"], "Hanya file gambar (jpg/png/webp/gif) yang diperbolehkan."),
            FileSize(),
        ],
    )
    submit = SubmitField("Update Account")

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError("That username is already taken.")

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError("That email is already registered.")


# ------------------------------------------------------------------
# 4. CHANGE PASSWORD FORM
# ------------------------------------------------------------------
class ChangePasswordForm(FlaskForm):
    old_password = PasswordField("Password Lama", validators=[DataRequired()])
    new_password = PasswordField(
        "Password Baru",
        validators=[
            DataRequired(),
            Length(min=8, max=72),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[\W_]).+$",
                message="Minimal 8 karakter, 1 Huruf Besar, 1 Angka, 1 Simbol.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Konfirmasi Password",
        validators=[DataRequired(), EqualTo("new_password", message="Password tidak sama.")],
    )
    submit = SubmitField("Simpan Password")


# ------------------------------------------------------------------
# 5. REQUEST RESET PASSWORD FORM (BARU)
# ------------------------------------------------------------------
class RequestResetForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(message="Email wajib diisi."), 
                                    Email(message="Masukkan format email yang benar.")])
    submit = SubmitField('Minta Reset Password')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('Email tidak ditemukan. Silakan daftar akun terlebih dahulu.')


# ------------------------------------------------------------------
# 6. RESET PASSWORD FORM (BARU)
# ------------------------------------------------------------------
class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password Baru', 
                             validators=[
                                DataRequired(message="Password baru wajib diisi."),
                                Length(min=8, max=72),
                                Regexp(
                                    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[\W_]).+$",
                                    message="Minimal 8 karakter, 1 Huruf Besar, 1 Angka, 1 Simbol.",
                                )
                             ])
    confirm_password = PasswordField('Konfirmasi Password Baru',
                                     validators=[DataRequired(message="Konfirmasi password wajib diisi."), 
                                                 EqualTo('password', message="Konfirmasi password harus sama.")])
    submit = SubmitField('Reset Password')


# ------------------------------------------------------------------
# 7. CATEGORY FORM
# ------------------------------------------------------------------
class CategoryForm(FlaskForm):
    name = StringField(
        "Category Name",
        validators=[DataRequired(message="Category name is required."), Length(min=2, max=50)],
    )
    submit = SubmitField("Save Category")

    def validate_name(self, name):
        category = Category.query.filter_by(name=name.data).first()
        if category:
            raise ValidationError("That category name already exists. Try another name.")


# ------------------------------------------------------------------
# 8. ITEM / PRODUCT FORM
# ------------------------------------------------------------------
class ItemForm(FlaskForm):
    category = SelectField("Category", choices=[], coerce=int, validators=[DataRequired(message="Category is required.")])
    name = StringField("Item Name", validators=[DataRequired(message="Item name is required."), Length(max=100)])
    description = TextAreaField("Specifications / Description", validators=[DataRequired(message="Description is required.")])
    price_per_hour = DecimalField("Price Per Hour (IDR)", validators=[DataRequired(message="Price per hour is required.")], places=2)
    price_per_day = DecimalField("Price Per Day (IDR)", validators=[DataRequired(message="Price per day is required.")], places=2)
    stock = IntegerField("Stock Quantity", validators=[DataRequired(message="Stock quantity is required.")])
    picture = FileField(
        "Upload Item Image",
        validators=[
            FileAllowed(["jpg", "jpeg", "png", "webp"], "Hanya file gambar (jpg/png/webp) yang diperbolehkan."),
            FileSize(5 * 1024 * 1024),
        ],
    )
    submit = SubmitField("Save Item")


# ------------------------------------------------------------------
# 9. CHECKOUT FORM
# ------------------------------------------------------------------
class CheckoutForm(FlaskForm):
    pickup_date = DateField("Pickup Date", validators=[DataRequired(message="Pickup date is required.")], format="%Y-%m-%d")
    submit = SubmitField("Place Order Now")

    def validate_pickup_date(self, pickup_date):
        if pickup_date.data < date.today():
            raise ValidationError("Pickup date cannot be in the past.")


# ------------------------------------------------------------------
# 10. ADD STAFF FORM
# ------------------------------------------------------------------
class AddStaffForm(FlaskForm):
    username = StringField("Staff Username", validators=[DataRequired(message="Username is required."), Length(min=2, max=20)])
    email = StringField("Staff Email", validators=[DataRequired(message="Email is required."), Email(message="Please enter a valid email address.")])
    password = PasswordField("Initial Password", validators=[DataRequired(message="Password is required."), Length(min=8)])
    submit = SubmitField("Add New Staff")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("That username is already taken.")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("That email is already registered.")


# ------------------------------------------------------------------
# 11. EDIT USER FORM (Admin)
# ------------------------------------------------------------------
class EditUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    
    phone = StringField("WhatsApp", validators=[Length(min=10, max=15), Regexp(r'^[0-9]+$')])

    role = SelectField("Role", choices=[("penyewa", "Penyewa"), ("staff", "Staff"), ("admin", "Admin")], validators=[DataRequired()])
    submit = SubmitField("Update User")

    def __init__(self, original_username=None, original_email=None, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email

    def validate_username(self, username):
        if username.data != (self.original_username or ""):
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError("That username is already taken.")

    def validate_email(self, email):
        if email.data != (self.original_email or ""):
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError("That email is already registered.")


# ------------------------------------------------------------------
# 12. PAYMENT PROOF UPLOAD FORM
# ------------------------------------------------------------------
class PaymentUploadForm(FlaskForm):
    proof = FileField(
        "Upload Payment Proof",
        validators=[
            FileRequired(message="You must upload a payment proof."),
            FileAllowed(["jpg", "jpeg", "png", "pdf"], "Allowed: jpg, png, pdf"),
            FileSize(10 * 1024 * 1024),  # 10 MB max
        ],
    )
    submit = SubmitField("Confirm Payment")