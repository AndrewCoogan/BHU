from flask import Flask, render_template, url_for
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Length
from wtforms.fields import *

app = Flask(__name__)

class HouseInput(FlaskForm):
    address = StringField('Username', validators=[DataRequired(), Length(1, 100)])
    submit = SubmitField()

@app.route('/')
def main_page():
    return render_template('index.html')

@app.route('/about', methods=['GET', 'POST'])
def about_form():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)