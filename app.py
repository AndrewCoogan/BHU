from flask import Flask, render_template, request, url_for, redirect, session, flash
from flask_wtf import FlaskForm
from wtforms.fields import IntegerField, SubmitField, RadioField, DecimalField
from flask_bootstrap import Bootstrap5
import secrets
import os

from BHU.API_Calls import _flask_get_UserHome
from BHU import get_HousesOfInterest, get_PropertyDetail
from BHU import GeoData, FeatureGenerator
from BHU.KerasModelToggle import KerasModelToggle
from BHU.KerasTransformers import generate_keras_pipeline

app = Flask(__name__)
bootstrap = Bootstrap5(app)
app.secret_key = secrets.token_hex()

'''
GET : This method pulls specific information form the webserver (just to view it)
POST : This method sends data from the user to the server.

Instagram users scrolling are GETTING, when they post a photo, they POST.

I will need GET and POST in anything the user is submitting, like index.html.

select = SelectField(choices=[('dog', 'Dog'), ('cat', 'Cat'), ('bird', 'Bird'), ('alien', 'Alien')])

When we get further, we should have a start over button, popping the variables and loading the main page.

On the main page--list caveats: single family, etc.

Bottom of Attributes, or the toggle page, pictures of the house, links should be around.
'''

def generate_initial_user_parameters(features, price_from_API):
    class DollarField(DecimalField):
        def process_formdata(self, valuelist):
            if len(valuelist) == 1:
                self.data = [valuelist[0].strip('$').replace(',', '')]
            else:
                self.data = []

            super(DollarField).process_formdata(self.data)

    class UserHomeForm(FlaskForm):
        year_built = IntegerField("Year Built")
        sqft = IntegerField("Square Footage")
        lot_sqft = IntegerField("Lot Square Footage")
        beds = IntegerField("Beds")
        full_baths = IntegerField("Full Baths")
        three_qtr_baths = IntegerField("3/4 Baths")
        half_baths = IntegerField("1/2 Baths")
        qtr_bath = IntegerField("1/4 Baths")
        garage = RadioField("Garage?", choices=[('yes', 'Yes'), ('no', 'No')])
        new_construction = RadioField("New Construction?",choices=[('yes', 'Yes'), ('no', 'No')])
        price = IntegerField("Price")
        submit = SubmitField()
        cancel = SubmitField()

    uhf = UserHomeForm()
    uhf.year_built.default = features.get('year_built') or 0
    uhf.sqft.default = features.get('sqft') or 0
    uhf.lot_sqft.default = features.get('lot_sqft') or 0
    uhf.beds.default = features.get('beds') or 1
    uhf.full_baths.default = features.get('baths_full') or 0
    uhf.three_qtr_baths.default = features.get('baths_3qtr') or 0
    uhf.half_baths.default = features.get('baths_half') or 0
    uhf.qtr_bath.default = features.get('baths_1qtr') or 0
    uhf.garage.default = 'yes' if features.get('garage') or 0 > 0 else 'no'
    uhf.new_construction.default = 'yes' if features.get('new_construction') else 'no'
    uhf.price.default = price_from_API
    uhf.process()
    return uhf

def get_keras_model(fg):
    keras_pipeline, target_transformed = generate_keras_pipeline(fg)

    keras_pipeline.set_params(**{
        'keras_model__load_model_if_available' : True,
        'keras_model__update_model' : False,
        'keras_model__save_model' : False
    })

    keras_pipeline.fit(fg.features, target_transformed)
    return keras_pipeline

@app.route('/', methods=['GET', 'POST'])
def main_page():
    if request.method == 'POST':
        if request.form['submit_button'] == 'submit-address':
            address = request.form.get("address")
            user_home = _flask_get_UserHome(address)
            # Now we have a users address and attributes, or a list of dictionaries.
            if isinstance(user_home, dict):
                # We have a good address to start modeling.
                session['user_home'] = user_home
                return redirect(url_for('verify_address_attributes'))
            # If we are here, we know it was an ambiguous call.
            multiple_addresses = [a['full_address'][0] for a in user_home]
            session['addresses'] = multiple_addresses
            return redirect(url_for('choose_address'))
    return render_template('index.html')

@app.route('/choose/', methods=['GET', 'POST'])
def choose_address():
    if request.method == 'POST':
        if request.form['submit_button'] == 'submit-address':
            selected_address = request.form.get("options")
            # If the user selects none, go back to home page.
            if selected_address == 'none':
                return redirect(url_for('main_page'))
            session['user_home'] = _flask_get_UserHome(selected_address)
            # Is the city covered by BHU?
            user_choice_valid, city, state = valid_location()
            # If not, throw an error and go back to the home page.
            if not user_choice_valid:
                flash(f'Unfortunately, there is no working model currently available for {city}, {state}.', 'warning')
                return redirect(url_for('main_page'))
            # If yes, lets load the models and proceed.
            return redirect(url_for('verify_address_attributes'))
    return render_template('choose.html')

@app.route('/attributes/', methods=['GET', 'POST'])
def verify_address_attributes():
    if request.method == 'GET':
        user_home_details = get_PropertyDetail(session.get('user_home', {}).get('property_id'))
        hoi = get_HousesOfInterest(session.get('user_home'), n=2000, listed_to_sold_ratio=0.3, verbose=True)
        gd = GeoData(hoi['geo'])
        fg = FeatureGenerator(houses = hoi['houses'], gd=gd, user_home=user_home_details)
        session['fg'] = fg # This is now immutable (I think???)
        user_form = generate_initial_user_parameters(fg.user_features, fg.user_home_formatted.price)
        # I should do price here as well.
        return render_template('attributes.html', UserHomeForm = user_form)
    elif request.method == 'POST':
        # Here we need to read in the users values and update them. We should assume we need to update them all.
        if request.form.get('submit') or '' == 'Submit':
            # I need to pull in all of the info from the web form.
            fg = session.pop('fg', None)
            fg.user_features.year_built = request.form.get('year_built') or 0
            fg.user_features.sqft = request.form.get('sqft') or 0
            fg.user_features.lot_sqft = request.form.get('lot_sqft') or 0
            fg.user_features.beds = request.form.get('beds') or 1
            fg.user_features.full_baths = request.form.get('baths_full') or 0
            fg.user_features.three_qtr_baths = request.form.get('baths_3qtr') or 0
            fg.user_features.half_baths = request.form.get('baths_half') or 0
            fg.user_features.qtr_bath = request.form.get('baths_1qtr') or 0
            fg.user_features.garage = 'yes' if request.form.get('garage') or 0 > 0 else 'no'
            fg.user_features.new_construction = 'yes' if request.form.get('new_construction') else 'no'
            fg.user_target = request.form.get('price') or fg.user_home_formatted.price
            session['fg'] = fg
            return redirect(url_for('toggle_model'))
        return redirect(url_for('main_page'))
    flash(f'Something horribly wrong happened, sending you back to a safe place.', 'warning')
    return redirect(url_for('main_page'))

@app.route('/toggle/', methods=['GET', 'POST'])
def toggle_model():
    if request.method == "GET":
        # This is showing the user the options.
        if 'keras_model' not in session:
            session['keras_model'] = generate_keras_pipeline(session['fg'])

        if 'kmt' in session:
            kmt = session.pop('kmt', None)
        else:
            kmt = KerasModelToggle(model=session['keras_model'], fg=session['fg'])

        toggle = {}
        toggle['beds'] = request.form.get('beds') or kmt.fg.user_features.get('beds')
        toggle['baths_full'] = request.form.get('baths_full') or kmt.fg.user_features.get('baths_full')
        toggle['three_qtr_baths'] = request.form.get('baths_3qtr') or kmt.fg.user_features.get('baths_full')
        toggle['half_baths'] = request.form.get('baths_half') or kmt.fg.user_features.get('baths_full')
        toggle['qtr_bath'] = request.form.get('baths_1qtr') or kmt.fg.user_features.get('baths_full')
        toggle['garage'] = 'yes' if request.form.get('garage') or 0 > 0 else 'no'
        kmt.modify_attributes(**toggle)

        

        return render_template('attributes.html', UserHomeForm = user_form)
    if request.method == "POST":
        # This is where we set up a new session['user_model']

    pass

@app.route('/about/', methods=['GET', 'POST'])
def about_form():
    return render_template('about.html')

def valid_location(session = session):
    city = session.get('user_home', {}).get('city') or ''
    state = session.get('user_home', {}).get('state_code') or ''
    model_code = f'{city.upper()}_{state.upper()}'
    model_location = 'BHU/Saved Results/KerasModel/'
    available_models = os.listdir(model_location)
    return (True if model_code + '.pkl' in available_models else False, city, state)

if __name__ == '__main__':
    app.run(debug=True)