from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, send, emit, join_room
from models import db, User, Message, PrivateMessage, Room, BlockedUser
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "chat-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chat.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
online_users = {}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

with app.app_context():
    db.create_all()
    if Room.query.count() == 0:
        for r in ["العامة", "العراق", "تركيا", "الأصدقاء", "الترحيب"]:
            db.session.add(Room(name=r))
        db.session.commit()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        gender = request.form.get("gender")
        age = request.form.get("age")
        status = request.form.get("status")
        room = request.form.get("room", "العامة")
        allow_private = True if request.form.get("allow_private") else False
        allow_comments = True if request.form.get("allow_comments") else False

        if not name:
            return redirect(url_for("login"))

        if BlockedUser.query.filter_by(name=name).first():
            return "تم حظر هذا المستخدم من الإدارة"

        avatar = "default.png"
        file = request.files.get("avatar")
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            avatar = filename

        user = User.query.filter_by(name=name).first()
        if not user:
            user = User(name=name, gender=gender, age=age, status=status, avatar=avatar,
                        allow_private=allow_private, allow_comments=allow_comments)
            db.session.add(user)
        else:
            user.gender = gender
            user.age = age
            user.status = status
            user.allow_private = allow_private
            user.allow_comments = allow_comments
            if avatar != "default.png":
                user.avatar = avatar

        db.session.commit()
        session["user_id"] = user.id
        session["name"] = user.name
        session["room"] = room
        return redirect(url_for("chat"))

    rooms = Room.query.all()
    return render_template("login.html", rooms=rooms)

@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    room = session.get("room", "العامة")
    messages = Message.query.filter_by(room=room).order_by(Message.created_at.asc()).limit(100).all()
    users = User.query.order_by(User.name.asc()).all()
    rooms = Room.query.all()
    blocked = [b.name for b in BlockedUser.query.all()]
    return render_template("chat.html", user=user, messages=messages, users=users, rooms=rooms, current_room=room, blocked=blocked)

@app.route("/change_room/<room>")
def change_room(room):
    session["room"] = room
    return redirect(url_for("chat"))

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    return render_template("profile.html", user=user)

@app.route("/admin")
def admin():
    users = User.query.all()
    messages = Message.query.order_by(Message.created_at.desc()).limit(200).all()
    blocked = BlockedUser.query.all()
    rooms = Room.query.all()
    return render_template("admin.html", users=users, messages=messages, blocked=blocked, rooms=rooms)

@app.route("/admin/delete_message/<int:message_id>")
def delete_message(message_id):
    msg = Message.query.get(message_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/block_user/<name>")
def block_user(name):
    if not BlockedUser.query.filter_by(name=name).first():
        db.session.add(BlockedUser(name=name))
        db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/unblock_user/<int:block_id>")
def unblock_user(block_id):
    b = BlockedUser.query.get(block_id)
    if b:
        db.session.delete(b)
        db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/add_room", methods=["POST"])
def add_room():
    name = request.form.get("room_name", "").strip()
    if name and not Room.query.filter_by(name=name).first():
        db.session.add(Room(name=name))
        db.session.commit()
    return redirect(url_for("admin"))

@app.route("/upload_chat_image", methods=["POST"])
def upload_chat_image():
    if "user_id" not in session:
        return jsonify({"ok": False})
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"ok": False})
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    url = "/static/uploads/" + filename
    name = session.get("name", "زائر")
    room = session.get("room", "العامة")
    html = f'<img src="{url}" class="chat-img">'
    user = User.query.filter_by(name=name).first()
avatar = user.avatar if user else "default.png"
msg = Message(user_name=name, avatar=avatar, message=html, room=room, is_image=True)
    db.session.add(msg)
    db.session.commit()
    socketio.emit("message", {"name": name, "avatar": avatar, "message": html}, room=room)
    return jsonify({"ok": True, "url": url})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@socketio.on("connect")
def connect():
    name = session.get("name", "زائر")
    room = session.get("room", "العامة")
    join_room(room)
    online_users[request.sid] = {"name": name, "room": room}
    room_users = [u["name"] for u in online_users.values() if u["room"] == room]
    emit("online_users", room_users, room=room)
    emit("online_count", len(room_users), room=room)
    send({"name": "النظام", "message": f"{name} دخل غرفة {room}"}, room=room)

@socketio.on("disconnect")
def disconnect():
    info = online_users.get(request.sid, {"name": "زائر", "room": "العامة"})
    name = info["name"]
    room = info["room"]
    online_users.pop(request.sid, None)
    room_users = [u["name"] for u in online_users.values() if u["room"] == room]
    emit("online_users", room_users, room=room)
    emit("online_count", len(room_users), room=room)
    send({"name": "النظام", "message": f"{name} خرج من الشات"}, room=room)

@socketio.on("message")
def message(data):
    name = session.get("name", "زائر")
    room = session.get("room", "العامة")
    text = data.get("message", "").strip()
    if not text:
        return
    if BlockedUser.query.filter_by(name=name).first():
        return
    user = User.query.filter_by(name=name).first()
avatar = user.avatar if user else "default.png"
msg = Message(user_name=name, avatar=avatar, message=text, room=room)
    db.session.add(msg)
    db.session.commit()
    send({"name": name, "avatar": avatar, "message": text}, room=room)

@socketio.on("private_message")
def private_message(data):
    sender = session.get("name", "زائر")
    receiver = data.get("receiver")
    text = data.get("message", "").strip()
    if not receiver or not text:
        return
    target = User.query.filter_by(name=receiver).first()
    if target and not target.allow_private:
        emit("private_message", {"sender": "النظام", "receiver": sender, "message": "هذا المستخدم لا يسمح بالخاص"})
        return
    pm = PrivateMessage(sender=sender, receiver=receiver, message=text)
    db.session.add(pm)
    db.session.commit()
    emit("private_message", {"sender": sender, "receiver": receiver, "message": text}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)

PROJECT_AUTHOR = "Orhan Jawdat"
PROJECT_VERSION = "1.0"


PROJECT_AUTHOR = "Orhan Jawdat"
PROJECT_VERSION = "1.0"

