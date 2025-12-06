# app/forms.py  (FULL REPLACE)
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
    - If max_size_bytes is None, read current_app.config['MAX_UPLOAD_IMAGE_BYTES']
      (fallback to 5MB) at validation time (so no current_app access at import).
    - Best-effort measurement: seeks stream to determine size if possible.
    """
    def _file_size(form, field):
        f = getattr(field, "data", None)
        if not f:
            return  # nothing uploaded

        # determine limit at runtime (app context must exist at validation time)
        try:
            if max_size_bytes is None:
                limit = int(current_app.config.get("MAX_UPLOAD_IMAGE_BYTES", 5 * 1024 * 1024))
            else:
                limit = int(max_size_bytes)
        except Exception:
            limit = 5 * 1024 * 1024

        # attempt to measure stream size (best-effort)
        try:
            size = None
            stream = getattr(f, "stream", None)
            if stream and hasattr(stream, "seek") and hasattr(stream, "tell"):
                cur = stream.tell()
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(cur)
            else:
                # fallback to content_length metadata if present
                size = getattr(f, "content_length", None)

            # if we couldn't determine size, don't raise here (WSGI MAX_CONTENT_LENGTH will protect)
            if size is None:
                return

            if size > limit:
                # human-friendly message in MB
                mb = limit / (1024 * 1024)
                raise ValidationError(f"File terlalu besar. Maksimum {mb:.1f} MB.")
        except ValidationError:
            raise
        except Exception:
            # if measuring fails, don't block (server MAX_CONTENT_LENGTH should protect)
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
            Length(min=8, max=72, message="Password must be between 8 and 72 characters."),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[\W_]).+$",
                message="Must contain at least 1 uppercase, 1 lowercase, 1 number and 1 symbol.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(message="Please confirm your password."), EqualTo("password", message="Passwords must match.")],
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
    # Allow common image types; size limit default to config MAX_UPLOAD_IMAGE_BYTES (5MB fallback)
    picture = FileField(
        "Change Profile Picture",
        validators=[
            FileAllowed(["jpg", "jpeg", "png", "webp", "gif"], "Hanya file gambar (jpg/png/webp/gif) yang diperbolehkan."),
            FileSize(),  # no literal here — reads config at validation time
        ],
    )
    submit = SubmitField("Update Account")

    def validate_username(self, username):
        # only check if username changed
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
# 4. CATEGORY FORM
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
# 5. ITEM / PRODUCT FORM
# ------------------------------------------------------------------
class ItemForm(FlaskForm):
    # choices expected to be filled by view: form.category.choices = [(id, name), ...]
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
# 6. CHECKOUT FORM
# ------------------------------------------------------------------
class CheckoutForm(FlaskForm):
    pickup_date = DateField("Pickup Date", validators=[DataRequired(message="Pickup date is required.")], format="%Y-%m-%d")
    submit = SubmitField("Place Order Now")

    def validate_pickup_date(self, pickup_date):
        if pickup_date.data < date.today():
            raise ValidationError("Pickup date cannot be in the past.")


# ------------------------------------------------------------------
# 7. ADD STAFF FORM
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
# 8. EDIT USER FORM (used by admin)
# ------------------------------------------------------------------
class EditUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField("Email", validators=[DataRequired(), Email()])
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
# 9. PAYMENT PROOF UPLOAD FORM
# ------------------------------------------------------------------
class PaymentUploadForm(FlaskForm):
    proof = FileField(
        "Upload Payment Proof",
        validators=[
            FileRequired(message="You must upload a payment proof."),
            FileAllowed(["jpg", "jpeg", "png", "pdf"], "Allowed: jpg, png, pdf"),
            FileSize(10 * 1024 * 1024),  # 10 MB max for payment proofs
        ],
    )
    submit = SubmitField("Confirm Payment")
