from datetime import datetime, timedelta

from flask import Blueprint, Flask, jsonify, g, url_for
from sqlalchemy import func

from src.auth import teacher_required, auth_required
from src.db import db
from src.db.models import Classroom, Student, Session, Behaviour

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/stats', methods=['GET'])
@auth_required()
def dashboard_stats():
    role = g.current_user.role

    if role == "admin":
        # Admin: Global stats
        total_classes = Classroom.query.count()
        total_students = Student.query.count()
        active_sessions = Session.query.filter_by(status=True).count()
        recent_behaviors = Behaviour.query.filter(
            Behaviour.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
    else:
        # Teacher: Personal stats
        teacher_id = g.current_user.id

        total_classes = Classroom.query.filter_by(teacher_id=teacher_id).count()
        total_students = Student.query.filter_by(teacher_id=teacher_id).count()
        active_sessions = Session.query.join(Classroom)\
            .filter(Classroom.teacher_id == teacher_id, Session.status == True)\
            .count()
        recent_behaviors = Behaviour.query.join(Session).join(Classroom)\
            .filter(
                Classroom.teacher_id == teacher_id,
                Behaviour.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).count()

    return jsonify({
        "total_classes": total_classes,
        "total_students": total_students,
        "active_sessions": active_sessions,
        "recent_behaviors": recent_behaviors
    })

@bp.route('/behavior-summary', methods=['GET'])
@teacher_required
def behavior_summary():
    teacher_id = g.current_user.id

    behaviors = Behaviour.query.join(Session).join(Classroom)\
        .filter(Classroom.teacher_id == teacher_id)\
        .group_by(Behaviour.behaviour)\
        .with_entities(
            Behaviour.behaviour,
            func.count().label('count')
        ).all()

    return jsonify({b.behaviour: b.count for b in behaviors})

@bp.route('/recent-sessions', methods=['GET'])
@teacher_required
def recent_sessions():
    teacher_id = g.current_user.id

    sessions = Session.query.join(Classroom)\
        .filter(Classroom.teacher_id == teacher_id)\
        .order_by(Session.created_at.desc())\
        .limit(3)\
        .all()

    session_data = []
    for session in sessions:
        behavior_count = Behaviour.query.filter_by(session_id=session.id).count()
        session_data.append({
            "class_name": session.class_obj.name,
            "start_time": session.class_started_at.isoformat(),
            "behavior_count": behavior_count
        })

    return jsonify(session_data)

@bp.route('/top-classes', methods=['GET'])
@teacher_required
def top_classes():
    teacher_id = g.current_user.id
    high_classes = db.session.query(
        Classroom.name,
        func.count(Session.id).label('session_count')
    ).join(Session)\
     .filter(Classroom.teacher_id == teacher_id)\
     .group_by(Classroom.id)\
     .order_by(func.count(Session.id).desc())\
     .limit(3)\
     .all()

    return jsonify([
        {"class_name": c.name, "session_count": c.session_count}
        for c in high_classes
    ])


@bp.route('/page/stats', methods=['GET'])
@teacher_required
def teacher_stats():
    teacher_id = g.current_user.id
    BEHAVIOR_TYPES = ['hand-raising', 'reading', 'writing']  # Only these 3 behaviors

    # --- 1. Core Metrics ---
    total_classes = Classroom.query.filter_by(teacher_id=teacher_id).count()
    total_sessions = Session.query.join(Classroom) \
        .filter(Classroom.teacher_id == teacher_id) \
        .count()

    # --- 2. Behavior Distribution (All Time) ---
    behavior_counts = []
    for behavior in BEHAVIOR_TYPES:
        count = Behaviour.query.join(Session).join(Classroom) \
            .filter(
            Classroom.teacher_id == teacher_id,
            Behaviour.behaviour == behavior
        ) \
            .count()
        behavior_counts.append({"behavior": behavior, "count": count})

    # --- 3. Class-Wise Behavior Breakdown ---
    class_stats = []
    classes = Classroom.query.filter_by(teacher_id=teacher_id).all()
    for class_obj in classes:
        # Get total sessions for this class
        session_count = Session.query.filter_by(class_id=class_obj.id).count()

        # Get behavior counts for this class
        behaviors = []
        for behavior in BEHAVIOR_TYPES:
            count = Behaviour.query.join(Session) \
                .filter(
                Session.class_id == class_obj.id,
                Behaviour.behaviour == behavior
            ) \
                .count()
            behaviors.append({"behavior": behavior, "count": count})

        class_stats.append({
            "class_id": class_obj.id,
            "class_name": class_obj.name,
            "session_count": session_count,
            "behaviors": behaviors
        })

    # --- 4. Weekly Trends (Last 4 Weeks) ---
    weekly_trends = []
    for i in range(4, -1, -1):  # Last 5 weeks
        week_start = datetime.utcnow() - timedelta(weeks=i + 1)
        week_end = datetime.utcnow() - timedelta(weeks=i)

        weekly_data = {"week": week_start.strftime("%Y-%m-%d"), "behaviors": []}
        for behavior in BEHAVIOR_TYPES:
            count = Behaviour.query.join(Session).join(Classroom) \
                .filter(
                Classroom.teacher_id == teacher_id,
                Behaviour.behaviour == behavior,
                Behaviour.created_at >= week_start,
                Behaviour.created_at < week_end
            ) \
                .count()
            weekly_data["behaviors"].append({"behavior": behavior, "count": count})
        weekly_trends.append(weekly_data)

    return jsonify({
        "core_metrics": {
            "total_classes": total_classes,
            "total_sessions": total_sessions
        },
        "behavior_summary": behavior_counts,
        "class_performance": class_stats,
        "weekly_trends": weekly_trends
    })

@bp.route('/session-log', methods=['GET'])
@teacher_required
def session_log():
    teacher_id = g.current_user.id
    BEHAVIOR_TYPES = ['hand-raising', 'reading', 'writing']
    sessions = Session.query.join(Classroom)\
        .filter(Classroom.teacher_id == teacher_id)\
        .order_by(Session.class_started_at.desc())\
        .all()

    session_logs = []
    for session in sessions:
        duration_minutes = round(
            (session.created_at - session.class_started_at).total_seconds() / 60,
            1
        ) if session.created_at else 0.0
        behavior_counts = []
        for behavior in BEHAVIOR_TYPES:
            count = Behaviour.query.filter_by(
                session_id=session.id,
                behaviour=behavior
            ).count()
            behavior_counts.append({"behavior": behavior, "count": count})

        class_obj = Classroom.query.get(session.class_id)

        session_logs.append({
            "session_id": session.id,
            "class_id": session.class_id,
            "class_name": class_obj.name if class_obj else "Unknown",
            "start_time": session.class_started_at.isoformat(),
            "duration_minutes": duration_minutes,
            "status": "Active" if session.status else "Completed",
            "behaviors": behavior_counts
        })

    return jsonify({
        "sessions": session_logs,
        "total_sessions": len(sessions)
    })


@bp.route('/classes', methods=['GET'])
@teacher_required
def get_teacher_classes():
    teacher_id = g.current_user.id

    classes = Classroom.query.filter_by(teacher_id=teacher_id).all()

    class_data = []
    for class_obj in classes:
        active_session = Session.query.filter_by(
            class_id=class_obj.id,
            status=True
        ).first()

        class_data.append({
            'id': class_obj.id,
            'name': class_obj.name,
            'image': url_for('static', filename=f'uploads/{class_obj.image}'),
            'description': class_obj.description,
            'has_active_session': active_session is not None,
            'active_session_id': active_session.id if active_session else None
        })

    return jsonify(class_data)