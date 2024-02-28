# save this as app.py
from flask import Flask, Response
from flask import Flask, render_template
import mysql.connector
from flask import Flask, request, redirect, url_for
import qrcode, cv2, hashlib, os
from pyzbar.pyzbar import decode
from simhash import Simhash
import threading, time
from PIL import Image
import webbrowser
from flask import g

url_scanned = set()
reset_lock = threading.Lock()

camera = cv2.VideoCapture(0)  

app = Flask(__name__)
app.secret_key = 'secret_key'

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345",
    database="qr_python",
    port=3306,
)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create_page")
def viewCreate():
    return render_template("create.html")

#tim kiem ma QR
@app.route("/search")
def search_qr():
    mycurrsor = db.cursor()
    input_search =  request.args.get('data')
    sql = "SELECT * FROM diadiem WHERE ten LIKE %s"
    mycurrsor.execute(sql, (input_search,))
    myrs = mycurrsor.fetchall()
    print(len(myrs))
    if(len(myrs) == 0):
        return render_template("search.html")
    else:
        return render_template("search.html", data_search = myrs)

#trang list ma qr
@app.route("/manage")
def viewManage():
    mycursor = db.cursor()
    sql = "SELECT * FROM diadiem"
    mycursor.execute(sql,)
    myrs = mycursor.fetchall()
    return render_template("manage.html", data_list = myrs)
    
#lay ra thong tin can chinh sua
@app.route("/getQR", methods=['POST'])
def editQR():
    mycursor = db.cursor()
    data = request.json
    #print(data)
    sql = "SELECT * FROM diadiem WHERE id=%s"
    mycursor.execute(sql, (data,))
    myresult = mycursor.fetchall()
    #print(myresult)
    return myresult
    
#chinh sua
@app.route("/saveUpdate", methods=['POST'])
def saveEdit():
    mycursor = db.cursor()
    data = request.json
    ten = data.get('ten_input')
    url_qr = data.get('url_input')
    str_id_qr = data.get('id_input')
    id_qr = int(str_id_qr)
    sql = "UPDATE diadiem SET ten=%s, url_google_map=%s WHERE id=%s"
    mycursor.execute(sql, (ten, url_qr, id_qr),)
    db.commit()
    return "OK"

def find_name_img(id):
    mycursor = db.cursor()
    data = (id,)
    sql = "SELECT ten_anh from diadiem WHERE id=%s"
    mycursor.execute(sql, data)
    myresult = mycursor.fetchall()
    return myresult[0][0]

@app.route("/del_item", methods=['POST'])
def del_item():
    mycursor = db.cursor()
    data = request.json
    id_item  = data.get('id_del')
    print(id_item)
    img_name = find_name_img(id_item) + ".png"

    if img_name:
        img_path = os.path.join(app.static_folder, 'img', img_name)
        if os.path.exists(img_path):
            os.remove(img_path)
            print("Đã xóa tệp ảnh:", img_path)
        else:
            print("Tệp ảnh không tồn tại:", img_path)
    sql = "DELETE FROM diadiem WHERE id = %s"
    i = (id_item,)
    mycursor.execute(sql, i)
    db.commit()
    return "OK"
    
def reset_url_scanned():
    global url_scanned
    while True:
        time.sleep(4)
        with reset_lock:
            url_scanned.clear()
reset_thread = threading.Thread(target=reset_url_scanned)
reset_thread.daemon = True
reset_thread.start()


#nhan frame tu camera
def generate_frames():
    global url_scanned
    result_scan= ""
    while True:
        success, frame = camera.read() 
        if not success:
            break
        else:
            decoded_objects = decode(frame)
            for obj in decoded_objects:
                result_scan = obj.data.decode('utf-8')
                if result_scan not in url_scanned:
                    getURL(result_scan)
                    url_scanned.add(result_scan)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'  b'Content-Type: image/jpeg\r\n\r\n' + frame  ) 
@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame') 

def getURL(code):
    mycursor = db.cursor()
    sql = "SELECT url_google_map FROM diadiem WHERE code = %s"
    mycursor.execute(sql, (code, ))
    myresult = mycursor.fetchall()
    data= myresult[0][0]
    webbrowser.open_new(data)

#bat camera
@app.route("/on_cam", methods=["POST"])
def start_camera():
    global camera
    camera = cv2.VideoCapture(0)
    return "start"

#tat camera
@app.route("/off_cam", methods=["POST"])
def stop_camera():
    global camera
    if camera:
        camera.release()  
        cv2.destroyAllWindows() 
    return "stop"


@app.before_request
def before_request():
    g.message = None

#tao ma qr
@app.route("/create", methods=["POST"])
def createQRCode():
    name = request.form.get("input_name")
    location = request.form.get("input_location")
    img_name = request.form.get("input_name_img")
    #print("Ten hinh"+ img_name)
    code = Simhash(location).value
    #print("code la " + str(code) )
    if(checkExist(code) == False):
        data = code
        img = qrcode.make(data)
        path_save = "static/img/" + img_name
        img.save(path_save+'.png')
        mycursor = db.cursor()
        sql = "INSERT INTO diadiem (ten, url_google_map, code, ten_anh)  VALUES (%s, %s, %s, %s)"
        val = (name, location, code, img_name)
        mycursor.execute(sql, val)
        db.commit()
        message_success = "Thành công"
        return render_template("create.html", message_success = message_success)
    else : 
        print("Khong them vao db")
        message_exist = "Đã tồn tại"
        return render_template("create.html", message_exist = message_exist)
def checkExist(code):
    mycursor = db.cursor()
    sql = "SELECT * FROM diadiem WHERE code=%s"
    mycursor.execute(sql, (code, ))
    myresult = mycursor.fetchall()
    if len(myresult) > 0:
        return True
    else :
        return False
def allowed_file(filename):
    # Kiểm tra tệp có phải là hình ảnh hay ko 
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


#quet ma bang hinh anh
@app.route("/scanimage", methods=["POST"])
def scan_img():
    file = request.files['scan_img']
    if file.filename == '':
        return 'No selected file'
    if file and allowed_file(file.filename):
        # lưu hình vào static/scan_img
        file_path = 'static/scan_img/' + file.filename
        file.save(file_path)
        
        img = cv2.imread(file_path)
        detect = cv2.QRCodeDetector()
        
        #code cua ma qr
        value, points, straight_qrcode = detect.detectAndDecode(img)
        sql = "SELECT url_google_map FROM diadiem WHERE code=%s"
        mycursor = db.cursor()
        mycursor.execute(sql, (value,))
        myresult = mycursor.fetchall()
        data = myresult[0][0]
        print(data)
        webbrowser.open_new(data)
    return redirect("/")
    #return render_template("create.html", data=value)
    
        

if __name__ == "__main__":
    app.run(debug=True)