import os.path
import uuid
from datetime import datetime, UTC, timedelta
from flask import Blueprint, request, jsonify, g, url_for
from pymsgbox import password
from werkzeug.security import gen_salt

from ...auth import teacher_required
from ...db.models import Teacher, Classroom
import bcrypt
from ...db import db
from jwt import JWT
from jwt.jwk import OctetJWK
from ...config import Config
from ...utils.uploads import upload_images

bp = Blueprint('teacher', __name__, url_prefix='/teacher')

secret = Config.SECRET_KEY
signing_key = OctetJWK(secret.encode())

jwt_instance = JWT()


def generate_token(user_id, role, first_name):
    if isinstance(user_id, uuid.UUID):
        user_id = str(user_id)

    expiration_time = int((datetime.now(UTC) + timedelta(hours=2)).timestamp())

    payload = {
        'user_id': user_id,
        'role': role,
        'first_name': first_name,
        'exp': expiration_time
    }
    token = jwt_instance.encode(payload, signing_key, alg='HS256')
    return token


@bp.route('/signup', methods=['POST'])
def create_teacher():
    data = request.get_json()

    if not data or 'first_name' not in data or 'last_name' not in data or 'email' not in data or password is None:
        return jsonify({
            'message': 'First name, last name and email are required'
        }), 400

    if Teacher.query.filter_by(email=data['email']).first():
        return jsonify({
            'message': 'Email already exists'
        }), 400

    teacher = Teacher(
        id = uuid.uuid4(),
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    )

    if 'password' not in data or not data['password']:
        return jsonify({
            'message': 'Password is required'
        }), 400

    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), salt)
    teacher.password_hash = password_hash.decode('utf-8')

    db.session.add(teacher)
    db.session.commit()

    return jsonify({
        'message': 'Teacher created successfully',
        'teacher_id': str(teacher.id)
    }), 201


@bp.route('/login-teacher', methods=['POST'])
def login_teacher():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({
            'message': 'Email and password are required'
        }), 400

    email = data['email']
    password = data['password']

    teacher = Teacher.query.filter_by(email=email).first()
    if not teacher or not bcrypt.checkpw(password.encode('utf-8'), teacher.password_hash.encode('utf-8')):
        return jsonify({
            'message': 'Email or password incorrect'
        }), 401

    return jsonify({
        'message': 'Login successful',
        'token': generate_token(teacher.id, teacher.role, teacher.first_name)
    }), 200


@bp.route('/create-class', methods=['POST'])
@teacher_required
def create_class():
    # Validate input
    if not request.form.get('class_name'):
        return jsonify({'message': 'Class name is required'}), 400

    if 'image' not in request.files:
        return jsonify({'message': 'Image is required'}), 400

    # Process data
    class_name = request.form.get('class_name')
    image = request.files['image']
    description = request.form.get('description', '')

    # Validate image (optional but recommended)
    if image.filename == '':
        return jsonify({'message': 'No selected image file'}), 400

    # Upload image and handle potential errors
    try:
        file_name = upload_images(image)
    except Exception as e:
        return jsonify({'message': f'Image upload failed: {str(e)}'}), 400
    new_class = Classroom(
        teacher_id=g.current_user.id,  # No need to convert to string
        name=class_name,
        image=file_name,
        description=description,
        id=uuid.uuid4()
    )

    print("Current User ID:", g.current_user.id)  # Check if this is a valid UUID
    print("Type of ID:", type(g.current_user.id))
    # Commit to database
    try:
        db.session.add(new_class)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500

    return jsonify({
        'message': 'Class created successfully',
        'class_id': str(new_class.id)  # Return UUID as string
    }), 201

@bp.route('/list-all', methods=["GET"])
@teacher_required
def get_teacher_classes():
    teacher_id = g.current_user.id
    classes = Classroom.query.filter_by(teacher_id=teacher_id).all()

    # Convert classes to a list of dictionaries for JSON serialization
    classes_list = [{
        'id': str(cls.id),
        'name': cls.name,
        'image': url_for('static', filename=f'uploads/{cls.image}'),
        'description': cls.description,
        'teacher_id': str(cls.teacher_id)
    } for cls in classes]
    return jsonify(classes_list), 200