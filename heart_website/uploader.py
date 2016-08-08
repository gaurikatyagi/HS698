from flask import Flask, render_template, request, url_for, flash, session, redirect
import os
import data_analysis
import pandas as pd
import csv
import matplotlib.pyplot as plt

app = Flask(__name__)
ALLOWED_EXTENSIONS = ["csv"]
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath( __file__ )), "static", "data")
USERNAME = "admin"
PASSWORD = "gt"
SECRET_KEY = "development key"

app.config.from_object(__name__)

def allowed_file(filename):
    return ('.' in filename) and (filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS)

def find_csv_filenames( suffix= ".csv" ):
    filenames = os.listdir(UPLOAD_FOLDER)
    return [ filename for filename in filenames if filename.endswith(suffix) ]

def data_avg():
    data = data_analysis.read_data(session["filename"])
    frequency = data_analysis.calc_freq_rate(data)
    filtered = data_analysis.butter_lowpass_filter(data["hart"], 2.5, frequency, 5)
    data['hart'] = filtered
    roll_mean_data = data_analysis.rolling_mean(data, window_size=0.75, frequency=frequency)
    roll_mean_data.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "temp", "moving_avg.csv"),
                          index = False)
    return roll_mean_data, frequency

@app.route('/')
def home():
    session["logged_in"] = False
    return render_template("html/pages/login.html")

@app.route("/login")
def login():
    session.pop("logged_in", None)
    return render_template("html/pages/login.html")

@app.route("/dashboard", methods = ["GET"])
def dashboard():
    file_info = os.path.join(UPLOAD_FOLDER, "uploaded_info.csv")
    data = pd.read_csv(file_info)
    # print data.head()
    gender = data["gender"]
    dob = data["dob"]
    patient_name = data["patient_name"]
    filename = data["filename"]
    return render_template("html/pages/dashboard.html", patient_name=patient_name,
                           dob=dob, gender=gender, filename = filename)

@app.route("/locked", methods = ["GET"])
def locked():
    return render_template("html/pages/locked.html")

@app.route("/profile", methods = ["GET"])
def profile():
    return redirect(url_for("csvfiles"))

@app.route("/blank", methods = ["GET", "POST"])
def blank():
    return render_template("html/pages/blank.html")

@app.route("/login_check", methods = ["GET", "POST"])
def login_check():
    error = None
    if request.method == "POST":
        if request.form["password"] != app.config["PASSWORD"]:
            error = "Invalid Password"
            return render_template("html/pages/login.html")
        elif "login_page" in request.form:
            if request.form["username"] != app.config["USERNAME"]:
                error = "Invalid Username"
                return render_template("html/pages/login.html")
        else:
            session["logged_in"] = True
            session["file_name"] = None
            return redirect(url_for("dashboard"))

@app.route('/uploaded', methods=['GET', 'POST'])
def uploaded():
    if request.method == 'POST':
        # check if the post request has the file part
        session["success"] = False
        if "file" not in request.files:
            flash("No file part")
            return render_template("html/pages/404.html")
        # if user does not select file, browser also
        # submit a empty part without filename
        file = request.files["file"]
        if file.filename == '':
            flash('No selected file')
            return render_template("html/pages/404.html")
        if file and allowed_file(file.filename):
            # filename = file.filename
            file_save_name = request.form["file_name"]
            file_present = False
            file_csv = open(UPLOAD_FOLDER + "/uploaded_info.csv", 'rb')
            reader = csv.reader(file_csv)
            for row in reader:
                if row[0] == file_save_name:
                    file_present = True
                    break
            file_csv.close()
            comment = "File Uploaded"
            if file_present == False:
                reading_number = request.form["reading_number"]
                patient_name = request.form["patient_name"]
                gender = request.form["gender"]
                dob = request.form.get("dob")
                file_csv = open(UPLOAD_FOLDER+"/uploaded_info.csv", 'ab')
                writer = csv.writer(file_csv, quoting=csv.QUOTE_ALL)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_save_name))
                writer.writerow(["filename", "reading_number", "patient_name", "gender", "dob"])
                writer.writerow([file_save_name, reading_number, patient_name, gender, dob])
                file_csv.close()
            else:
                comment = "File Already Exists"
            session["success"] = True
            session["comment"] = comment
            return redirect(url_for("csvfiles"))
        else:
            flash("Wrong filetype")
            return render_template("html/pages/500.html")

@app.route("/csvfiles")
def csvfiles():
    file_names = find_csv_filenames()
    # entries = [dict(file = index, text = row) for index, row in enumerate(file_names)]
    file_info = os.path.join(UPLOAD_FOLDER, "uploaded_info.csv")
    data = pd.read_csv(file_info)
    # print data.head()
    file_names = data["filename"]
    number_readings = data["reading_number"]
    patient_name = data["patient_name"]
    # print patient_name


    flash("File Uploaded")
    if "comment" in session:
        return render_template("html/pages/profile.html", patient_name = patient_name,
                               number_readings = number_readings, file_names = file_names, comment = session["comment"])
    else:
        return render_template("html/pages/profile.html", patient_name=patient_name,
                               number_readings=number_readings, file_names=file_names)

@app.route("/analyze/<filename>", methods = ["POST"])
def analyze(filename):
    if request.method == "POST":
        session["filename"] = filename
        data = data_avg()
        return redirect(url_for("peaks"))
    else:
        return render_template(url_for("html/pages/profile.html"))

@app.route('/moving_average', methods = ["POST"])
def moving_average():
    data = data_avg()
    return redirect(url_for("peaks"))

@app.route('/peaks', methods = ["GET", "POST"])
def peaks():
    roll_mean_data, frequency = data_avg()
    data_analysis.fit_peaks(roll_mean_data, frequency)
    data_analysis.calc_frequency_measures(roll_mean_data, frequency)
    data_analysis.time_measures["bpm"] = (len(data_analysis.signal_measures["R_positions"]) / (len(roll_mean_data["hart"]) / frequency) * 60)
    R_positions = data_analysis.signal_measures["R_positions"]
    ybeat = data_analysis.signal_measures["R_values"]
    bpm = data_analysis.time_measures["bpm"]
    fig = plt.figure()
    ax = fig.add_subplot(111)

    plt.title("Heart Rate signal with R-complexes")
    ax.plot(roll_mean_data["hart"], alpha=0.5, color='blue', label="raw signal", ls = '-')
    ax.plot(roll_mean_data["hart_rolling_mean"], color='orange', label="moving average", ls = '-.')
    ax.scatter(R_positions, ybeat, color='red', s= 3, label = "R-complexes")
    ax.legend(loc=4, framealpha=0.0)

    cur_axes = plt.gca()
    cur_axes.axes.get_xaxis().set_ticklabels([])
    if os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "temp", "peaks.png")):
        os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "temp", "peaks.png"))
    plt.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "temp", "peaks.png"),
                transparent=True, bbox_inches='tight', pad_inches=0)
    # del plt.figure
    return render_template("html/pages/show_signal.html", data_file = url_for("static", filename = "temp/moving_avg.csv"),
                           bpm = bpm, frequency = frequency, fig = url_for("static", filename = "temp/peaks.png"))

@app.route('/delete/<filename>/<index_val>', methods = ["POST"])
def delete(filename, index_val):
    file_remove_path = os.path.join(UPLOAD_FOLDER, filename)
    os.remove(file_remove_path)
    file_info = pd.read_csv(os.path.join(UPLOAD_FOLDER, "uploaded_info.csv"))
    os.remove(os.path.join(UPLOAD_FOLDER, "uploaded_info.csv"))
    file_info = file_info.drop(file_info.index[[index_val]])
    file_info.reindex()
    file_info.to_csv(os.path.join(UPLOAD_FOLDER, "uploaded_info.csv"))
    # return jsonify(filename, index_val, file_remove_path)
    return redirect(url_for("csvfiles"))

if __name__ == '__main__':
    app.run(debug=True , host='0.0.0.0', port=5003)