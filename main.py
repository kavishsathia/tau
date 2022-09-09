from flask import Flask, render_template, request, redirect, session
import sqlite3
import hashlib
import subprocess; from os.path import exists; from os import remove
import time; import random

app = Flask(__name__)
app.secret_key = "computing"

class Question():
    def __init__(self, l, index):
        attributes = l[index].split(",")
        if len(attributes) == 3:
            self.title = attributes[0]
            try:
                year = int(attributes[1])
            except:
                year = 0
            self.year = year
            self.topic = attributes[2]
            if index + 1 < len(l):
                self.question = l[index + 1]
            else:
                raise Exception
        else:
            raise Exception

def data_process(data):
    split_data = data.split("@qn@")
    split_data = [datum for datum in split_data if datum != ""]
    return_list = []
    for i in range(0, len(split_data), 2):
        try:
            return_list.append(Question(split_data, i))
        except:
            pass
    return return_list

@app.route('/', methods=['GET'])
def search_page():
    if 'username' in session:
        return render_template('index.html', data=session['username'])
    else:
        return render_template('index.html', data="")

@app.route('/results', methods=['POST'])
def results_page():
    search = request.form['search']
    search_arr = search.strip().split(" ")

    # parsing
    sql_string = "SELECT * from Question WHERE status = 'Success' AND "
    data = ()
    query = ""
    substring = 0
    while substring < len(search_arr) and search_arr[substring] not in ["-t", "-d", "-y"]:
        query = query + search_arr[substring] + " "
        substring += 1
    sql_string = sql_string + "contents LIKE ? AND "
    data = data + ("%" + query.strip() + "%",)
    register = ""
    for i in range(0, len(search_arr)):
        if search_arr[i] in ["-t", "-y"]:
            register = search_arr[i]
        elif register == "-t":
            data = data + ("%" + search_arr[i] + "%",)
            sql_string = sql_string + "topic LIKE ? AND "
        elif register == "-y":
            try:
                year = int(search_arr[i])
            except:
                year = 0
            data = data + (year,)
            sql_string = sql_string + "year = ? AND "

    # finding
    database = sqlite3.connect('questions.db')
    cursor = database.cursor()
    try:
        cursor.execute(sql_string[:-4], data)
        return_data = cursor.fetchall()
        database.close()
    except:
        database.close()
        return redirect("/error")

    if 'username' in session:
        return render_template('results.html', data=(return_data, session['username'], search))
    else:
        return render_template('results.html', data=(return_data, "", search))

@app.route('/contributions', methods=['GET'])
def contributions():
    if 'username' not in session:
        return redirect("/sign_in")
    database = sqlite3.connect('questions.db')
    sql_data = (session['username'],)
    try:
        contributions = database.execute(
            "SELECT * FROM Question WHERE username = ?",
            sql_data
        ).fetchall()
        database.close()
    except:
        database.close()
        return redirect("/error")
    return render_template('contributions.html', data=(contributions, session['username']))

@app.route('/error', methods=['GET'])
def error():
    if 'username' in session:
        return render_template('error.html', data=session['username'])
    else:
        return render_template('error.html', data="")

@app.route('/delete', methods=['POST'])
def delete():
    if 'username' not in session:
        return redirect("/sign_in")
    id = request.form.get("delete")
    database = sqlite3.connect('questions.db')
    sql_data = (id,session['username'])
    try:
        filename = database.execute(
            "SELECT file_name FROM Question WHERE id = ? AND username = ?",
            sql_data).fetchone()
    except:
        database.close()
        return redirect("/error")
    try:
        database.execute("DELETE FROM Question WHERE id = ? AND username = ?", sql_data)
        database.commit()
        database.close()
    except:
        database.close()
        return redirect("/error")
    if filename is not None:
        if exists(f"static/{filename[0]}.aux"): remove(f"static/{filename[0]}.aux")
        if exists(f"static/{filename[0]}.log"): remove(f"static/{filename[0]}.log")
        if exists(f"static/{filename[0]}.pdf"): remove(f"static/{filename[0]}.pdf")
        if exists(f"static/{filename[0]}-crop.pdf"): remove(f"static/{filename[0]}-crop.pdf")
        if exists(f"static/{filename[0]}.tex"): remove(f"static/{filename[0]}.tex")
    return redirect("/contributions")

@app.route('/upload', methods=['GET'])
def upload_page():
    if 'username' not in session:
        return redirect("/sign_in")
    details = (session['username'],)
    return render_template('upload.html', data=details)

@app.route('/upload_data', methods=['POST'])
def upload_data():
    if 'username' not in session:
        return redirect("/sign_in")
    contents = str(request.files['file'].read(), 'utf-8')
    data = data_process(contents)
    for datum in data:
        hash = str(hashlib.sha256(datum.question.encode('utf-8')).hexdigest())
        nonce = str(int(time.time()))
        rand = str(random.randint(0, 100000))
        try:
            file = open(f"static/{hash}-{nonce}-{rand}.tex", "w")
            file.write(datum.question)
        finally:
            file.close()
        subprocess.run(f"cd ~/tau/static/; pdflatex -halt-on-error -interaction=nonstopmode {hash}-{nonce}-{rand}.tex; pdfcrop {hash}-{nonce}-{rand}.pdf;", shell=True)
        database = sqlite3.connect('questions.db')
        cursor = database.cursor()
        try:
            if exists(f"static/{hash}-{nonce}-{rand}-crop.pdf"):
                sql_data = (datum.year, datum.topic, session['username'], f"{hash}-{nonce}-{rand}", datum.title, datum.question, 'Success')
                cursor.execute(f"INSERT INTO Question ('year', "
                               f"'topic', 'username', 'file_name', 'title', 'contents', 'status') VALUES (?, "
                               f"?, ?, ?, ?, ?, ?);", sql_data)
            else:
                sql_data = (datum.year, datum.topic, session['username'],
                           f"{hash}-{nonce}-{rand}", datum.title, datum.question,
                           'Error')
                cursor.execute(f"INSERT INTO Question ('year', "
                               f"'topic', 'username', 'file_name', 'title', 'contents', 'status') VALUES (?, "
                               f"?, ?, ?, ?, ?, ?);", sql_data)
            database.commit()
        finally:
            # we don't redirect to the error page here because the server will just choose to ignore faulty entry that causes the SQL to malfunction (quite rare)
            database.close()
    return redirect("/contributions")

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.form
    database = sqlite3.connect('questions.db')
    try:
        sqlData = (data['username'],)
        user = database.execute(f"SELECT * FROM User WHERE username = ?", sqlData).fetchone()
        database.close()
    except:
        database.close()
        return redirect("/error")
    userauth = data['username'] + data['password']
    userhash = str(hashlib.sha256(userauth.encode('utf-8')).hexdigest())
    if user is not None and user[0] == userhash:
        session['username'] = data['username']
        return redirect("/")
    else:
        return render_template("sign_in.html", data=("Invalid username or password",))


@app.route('/sign_up_data', methods=['POST'])
def sign_up_data():
    data = request.form
    if data['password'] != data['confirm_password']:
        return render_template("sign_up.html", data=("Passwords do not match",))
    else:
        userauth = data['username'] + data['password']
        userhash = str(hashlib.sha256(userauth.encode('utf-8')).hexdigest())
        database = sqlite3.connect('questions.db')
        try:
            sqlData = (data['username'],)
            user = database.execute(f"SELECT * FROM User WHERE username = ?;", sqlData).fetchone()
            if user is not None or data['username'] == "":
                return render_template("sign_up.html", data=("Use a different username",))
            else:
                try:
                    sqlData = (userhash, data['username'])
                    database.execute(f"INSERT INTO User (userhash, username) VALUES (?, ?);", sqlData)
                    session['username'] = data['username']
                    database.commit()
                    database.close()
                except:
                    database.close()
                    return redirect("/error")
        except:
            database.close()
            return redirect("/error")
    return redirect("/")


@app.route('/sign_up', methods=['GET'])
def sign_up():
    return render_template("sign_up.html", data=("",))

@app.route('/sign_in', methods=['GET'])
def sign_in():
    return render_template("sign_in.html", data=("",))

@app.route('/sign_out', methods=['GET'])
def sign_out():
    if 'username' in session: session.clear()
    return redirect("/")

@app.route('/about', methods=['GET'])
def about():
    return render_template("about.html")

@app.route('/help', methods=['GET'])
def help():
    return render_template("help.html")

app.run(host="0.0.0.0", port=5003, debug=True)