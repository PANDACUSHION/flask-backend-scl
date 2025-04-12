import os
import uuid

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func
from werkzeug.utils import secure_filename

from ...config import Config
from ...db import db
from ...db.models import Session, Behaviour, Classroom
from ...auth import teacher_required


bp = Blueprint('session', __name__, url_prefix='/session')


@bp.route('/create/<string:uuid_value>', methods=['POST', 'GET'])
@teacher_required
def create_or_check_session(uuid_value):
    try:
        if request.method == 'GET':
            session = Session.query.filter_by(class_id=uuid_value).order_by(Session.created_at.desc()).first()

            if not session:
                return jsonify({'message': 'No session found for this class.'}), 200

            if session.status:
                return jsonify({
                    'message': 'Session is already active.',
                    'session_id': str(session.id),
                    'status': True
                }), 200
            else:
                return jsonify({
                    'message': 'Session exists but is not active.',
                    'session_id': str(session.id)
                }), 200

        elif request.method == 'POST':
            existing_session = Session.query.filter_by(class_id=uuid_value, status=True).first()
            if existing_session:
                existing_session.status = False
                db.session.commit()
                return jsonify({
                    'message': 'Existing active session has been deactivated',
                    'session_id': str(existing_session.session_id)
                }), 200
            else:
                new_session = Session(
                    id=uuid.uuid4(),
                    session_id=uuid.uuid4(),
                    class_id=uuid_value,
                    status=True,
                )
                db.session.add(new_session)
                db.session.commit()

                return jsonify({
                    'message': 'Session created successfully',
                    'session_id': str(new_session.id)
                }), 201

        # Handle any other HTTP methods
        return jsonify({'message': 'Method not allowed'}), 405

    except Exception as e:
        db.session.rollback()  # Rollback on error
        return jsonify({'error': f"{str(e)}"}), 500

@bp.route('/detect/<string:session_id>', methods=['POST'])
@teacher_required
def create_detection(session_id):
    file = request.files.get("image")

    try:
        # Fetch the session based on session_id
        session = Session.query.get(session_id)

        if not session:
            return jsonify({'error': 'Session not found'}), 404

        if not session.status:
            return jsonify({'error': 'Session is not active'}), 400
        detection = True

        if detection:
            if not file:
                return jsonify({'error': 'No file provided'}), 400

            original_filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            upload_path = os.path.join(Config.IMAGE_PATH, unique_filename)
            file.save(upload_path)

            user_behaviour = Behaviour(
                id=uuid.uuid4(),
                session_id=session_id,
                x_axis=10,
                y_axis=20,
                w_axis=10,
                h_axis=20,
                confidence=0.5,
                image=unique_filename,
                behaviour='hand-raising'
            )

            db.session.add(user_behaviour)
            db.session.commit()

            analysis_response = {
                'id': user_behaviour.id,
                'behaviour': user_behaviour.behaviour,
                'x_axis': user_behaviour.x_axis,
                'y_axis': user_behaviour.y_axis,
                'w_axis': user_behaviour.w_axis,
                'h_axis': user_behaviour.h_axis,
                'confidence': user_behaviour.confidence,
                'image': user_behaviour.image
            }

            return jsonify({'message': 'Behaviour detected and saved successfully', 'analysis': analysis_response}), 200

        else:
            return jsonify({'message': 'No behaviour detected'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/stats/session/<string:session_id>', methods=['GET'])
@teacher_required
def get_session_stats(session_id):
    """Get behavior statistics for a specific session"""
    try:
        # Get basic session info
        session = db.session.query(Session).filter(Session.id == session_id).first()
        if not session:
            return jsonify({'message': 'Session not found'}), 404

        # Get behavior counts
        behavior_results = (
            db.session.query(Behaviour.behaviour, func.count(Behaviour.id))
            .filter(Behaviour.session_id == session_id)
            .group_by(Behaviour.behaviour)
            .all()
        )
        # Format results with default values
        stats = {
            'session_id': str(session_id),
            'class_id': str(session.class_id),
            'start_time': session.class_started_at.isoformat(),
            'behaviors': {b: c for b, c in behavior_results}
        }
        for behavior in ['hand-raising', 'writing', 'reading']:
            stats['behaviors'].setdefault(behavior, 0)

        return jsonify({'message': stats}), 200

    except Exception as e:
        return jsonify({'message': str(e)}), 400


@bp.route('/stats/classroom/<string:class_id>/sessions', methods=['GET'])
@teacher_required
def get_classroom_sessions_stats(class_id):
    try:
        classroom = db.session.query(Classroom).filter(Classroom.id == class_id).first()
        if not classroom:
            return jsonify({'message': 'Classroom not found'}), 404
        sessions = db.session.query(Session).filter(Session.class_id == class_id).all()
        session_ids = [str(s.id) for s in sessions]
        behavior_results = (
            db.session.query(Behaviour.behaviour, func.count(Behaviour.id))
            .join(Session)
            .filter(Session.class_id == class_id)
            .group_by(Behaviour.behaviour)
            .all()
        )
        stats = {
            'class_id': str(class_id),
            'session_count': len(sessions),
            'session_ids': session_ids,
            'total_behaviors': sum(c for _, c in behavior_results),
            'behaviors': {b: c for b, c in behavior_results}
        }

        # Ensure all expected behaviors are included
        for behavior in ['hand-raising', 'writing', 'reading']:
            stats['behaviors'].setdefault(behavior, 0)

        return jsonify({'message': stats}), 200

    except Exception as e:
        return jsonify({'message': str(e)}), 400


@bp.route('/stats/classroom/<string:class_id>/session/<string:session_id>', methods=['GET'])
@teacher_required
def get_classroom_session_stats(class_id, session_id):
    try:
        # Verify session belongs to classroom
        session = (
            db.session.query(Session)
            .filter(Session.id == session_id)
            .filter(Session.class_id == class_id)
            .first()
        )

        if not session:
            return jsonify({'message': 'Session not found in this classroom'}), 404

        # Reuse the session stats function
        return get_session_stats(session_id)

    except Exception as e:
        return jsonify({'message': str(e)}), 400
