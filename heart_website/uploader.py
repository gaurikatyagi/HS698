from flask import Flask, render_template, request, url_for, flash, session, redirect
import os
import data_analysis

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
    # path_to_dir = os.path.dirname(os.path.abspath(__file__))
    filenames = os.listdir(UPLOAD_FOLDER)
    return [ filename for filename in filenames if filename.endswith(suffix) ]

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
    return render_template("html/pages/dashboard.html")

@app.route("/locked", methods = ["GET"])
def locked():
    return render_template("html/pages/locked.html")

@app.route("/profile", methods = ["GET"])
def profile():
    return redirect(url_for("csvfiles"))
    # return render_template("html/pages/profile.html")

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
            # flash(message = "You are now logged in")
            return redirect(url_for("profile"))

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
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # flash("File Uploaded")
            session["success"] = True
            return redirect(url_for("csvfiles"))
            # return render_template("show_entries.html")
        else:
            flash("Wrong filetype")
            return render_template("html/pages/500.html")

@app.route("/csvfiles")
def csvfiles():
    file_names = find_csv_filenames()
    entries = [dict(file = index, text = row) for index, row in enumerate(file_names)]
    flash("File Uploaded")
    return render_template("html/pages/profile.html", entries = entries)

@app.route("/analyze/<filename>", methods = ["POST"])
def analyze(filename):
    # file_name = None
    if request.method == "POST":
        # filename = request.form["filename"]
        session["file_name"] = filename
        # return render_template("html/pages/orig.html", data_file = url_for("static/data", filename=filename))
        return render_template("html/pages/orig.html", data_file = url_for("static", filename="data/"+filename))
    else:
        return redirect(url_for("html/pages/profile.html"))

# @app.route('/about')
# def about():
#     return render_template('about.html')

@app.route('/moving_average', methods = ["POST"])
def moving_average():
    data = data_analysis.read_data(session["file_name"])
    frequency = data_analysis.calc_freq_rate(data)
    # print "Frequency of the data is: ", frequency
    filtered = data_analysis.butter_lowpass_filter(data["hart"], 2.5, frequency, 5)
    roll_mean_data = data_analysis.rolling_mean(data, window_size=0.75, frequency=frequency)
    roll_mean_data.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "temp", "moving_avg.csv"),
                          index = False)
    return render_template("data_and_average.html", data_file = url_for("static", filename = "temp/moving_avg.csv"))

@app.route('/peaks')
def r_complex():
    data = data_analysis.read_data(session["file_name"])
    frequency = data_analysis.calc_freq_rate(data)
    # print "Frequency of the data is: ", frequency
    filtered = data_analysis.butter_lowpass_filter(data["hart"], 2.5, frequency, 5)
    roll_mean_data = data_analysis.rolling_mean(data, window_size=0.75, frequency=frequency)
    roll_mean_data.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "moving_avg.csv"),
                          index=False)
    data_analysis.fit_peaks(roll_mean_data, frequency)
    data_analysis.calc_frequency_measures(roll_mean_data, frequency)
    data_analysis.time_measures["bpm"] = (len(data_analysis.signal_measures["R_positions"]) / (len(roll_mean_data["hart"]) / frequency) * 60)
    R_positions = data_analysis.signal_measures["R_positions"]
    ybeat = data_analysis.signal_measures["R_values"]
    return render_template("peaks.html", data_file=url_for("static", filename="moving_avg.csv"))

if __name__ == '__main__':
    app.run(debug=True)