const socket = io();
const messages = document.getElementById("messages");
const input = document.getElementById("messageInput");
const onlineUsers = document.getElementById("onlineUsers");
const privateBox = document.getElementById("privateMessages");
let mutedUsers = [];

socket.on("message", function(data){
    if(mutedUsers.includes(data.name)) return;
    const div = document.createElement("div");
    div.className = data.name === "النظام" ? "system" : "message";
    if(data.name === "النظام"){
        div.innerHTML = data.message;
    } else {
        const avatar = data.avatar || "default.png";
        const now = new Date();
const time = now.toLocaleString();

div.innerHTML =
'<img class="msg-avatar" src="/static/uploads/' + avatar + '" onerror="this.src=\'https://via.placeholder.com/40\'">' +
'<div class="msg-content">' +
'<div class="msg-header"><b>' + data.name + '</b><span class="msg-time">' + time + '</span></div>' +
data.message +
'</div>';
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    notifyUser(data.name + ": " + stripHtml(data.message));
});

socket.on("online_count", function(count){
    const el = document.getElementById("onlineCount");
    if(el) el.innerText = count;
});

socket.on("online_users", function(users){
    if(!onlineUsers) return;
    onlineUsers.innerHTML = "";
    users.forEach(u=>{
        const li = document.createElement("li");
        li.innerText = "🟢 " + u;
        onlineUsers.appendChild(li);
    });
});

socket.on("private_message", function(data){
    const div = document.createElement("div");
    div.className = "message private";
    const avatar = data.avatar || "default.png";
    div.innerHTML =
        '<img class="msg-avatar" src="/static/uploads/' + avatar + '" onerror="this.src=\'https://via.placeholder.com/40\'">' +
        '<div class="msg-content"><b>خاص من ' + data.sender + ' إلى ' + data.receiver + '</b><br>' + data.message + '</div>';
    privateBox.appendChild(div);
    notifyUser("رسالة خاصة من " + data.sender);
});

function sendMessage(){
    const text = input.value.trim();
    if(!text) return;
    socket.send({message:text});
    input.value = "";
}

function sendPrivate(){
    const receiver = document.getElementById("privateReceiver").value;
    const text = document.getElementById("privateInput").value.trim();
    if(!text) return;
    socket.emit("private_message", {receiver:receiver, message:text});
    document.getElementById("privateInput").value = "";
}

function showTab(name){
    document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
    document.getElementById(name+"Tab").classList.add("active");
}

function toggleMenu(){
    document.getElementById("sidebar").classList.toggle("open");
}

function startPrivate(name){
    showTab("private");
    document.getElementById("privateReceiver").value = name;
}

function muteUser(name){
    if(!mutedUsers.includes(name)) mutedUsers.push(name);
    alert("تم كتم " + name);
}

function uploadImage(){
    const file = document.getElementById("chatImage").files[0];
    if(!file) return;
    const form = new FormData();
    form.append("image", file);
    fetch("/upload_chat_image", {method:"POST", body:form});
}

function notifyUser(text){
    if(!("Notification" in window)) return;
    if(Notification.permission === "granted"){
        new Notification("الشات", {body:text});
    }
}

function stripHtml(html){
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || "";
}

if("Notification" in window && Notification.permission !== "granted"){
    Notification.requestPermission();
}

if(input){
    input.addEventListener("keypress", e=>{
        if(e.key === "Enter") sendMessage();
    });
}
