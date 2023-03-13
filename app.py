#type:ignore
from flask import Flask, render_template, request, url_for, redirect, session, flash
from flask_wtf import FlaskForm
from wtforms.fields import IntegerField, SubmitField, RadioField, DecimalField
from flask_bootstrap import Bootstrap5
import secrets
import os

from BHU.API_Calls import _flask_get_UserHome
from BHU import get_PropertyDetail
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

def generate_user_parameters(features, price_from_API = 0):
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
        start_over = SubmitField("Start Over?")

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

def get_keras_model(fg__targets, fg__features, fg__model_name):
    keras_pipeline, target_transformed = generate_keras_pipeline(fg__targets, fg__model_name)

    keras_pipeline.set_params(**{
        'keras_model__load_model_if_available' : True,
        'keras_model__update_model' : False,
        'keras_model__save_model' : False
    })

    keras_pipeline.fit(fg__features, target_transformed)
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
            session['model_name'] = f'{city.upper()}_{state.upper()}'
            return redirect(url_for('verify_address_attributes'))
    return render_template('choose.html')

@app.route('/attributes/', methods=['GET', 'POST'])
def verify_address_attributes():
    if request.method == 'GET':
        user_home_details = get_PropertyDetail(session.get('user_home', {}).get('property_id'))
        user_form = generate_user_parameters(fg.user_features, fg.user_home_formatted.price)
        # What do I need from feature generator?

        # session['fg__user_home_formatted'] = fg.user_home_formatted
        # ^^^ does not work because House is non-serializable
        # We will need .price, .address, cool, not so bad.
        session['fg__user_features'] = fg.user_features
        session['fg__user_home_formatted__price'] = fg.user_home_formatted.price
        session['fg__user_home_formatted__address'] = fg.user_home_formatted.address
        session['fg__features'] = fg.features
        session['fg__targets'] = fg.targets
        return render_template('attributes.html', UserHomeForm = user_form)
    elif request.method == 'POST':
        # Here we need to read in the users values and update them. We should assume we need to update them all.
        if request.form.get('submit') == 'Submit':
            # I need to pull in all of the info from the web form.
            user_features = session.pop('fg__user_features', None)
            user_features['year_built'] = request.form.get('year_built') or 0
            user_features['sqft'] = request.form.get('sqft') or 0
            user_features['lot_sqft'] = request.form.get('lot_sqft') or 0
            user_features['beds'] = request.form.get('beds') or 1
            user_features['full_baths'] = request.form.get('baths_full') or 0
            user_features['three_qtr_baths'] = request.form.get('baths_3qtr') or 0
            user_features['half_baths'] = request.form.get('baths_half') or 0
            user_features['qtr_bath'] = request.form.get('baths_1qtr') or 0
            user_features['garage'] = True if request.form.get('garage') or 0 > 0 else False
            user_features['new_construction'] = True if request.form.get('new_construction') else False
            session['fg__user_features'] = user_features
            print(session)
            if 'user_provided_price' not in session:
                session['user_provided_price'] = \
                    request.form.get('price') or session.get('fg__user_home_formatted').price or 0
                # This is just an over engineered way of waterfalling to make sure we get a price.
            return redirect(url_for('toggle_model'))
        return redirect(url_for('main_page'))
    flash(f'Something horribly wrong happened, sending you back to a safe place.', 'warning')
    return redirect(url_for('main_page'))

@app.route('/toggle/', methods=['GET', 'POST'])
def toggle_model():
    if request.method == "GET":
        # This is showing the user the options.
        if 'keras_model' not in session:
            session['keras_model'] = generate_keras_pipeline(
                fg__targets = session.get('fg__targets'), 
                fg__features = session.get('fg__features'), 
                fg__model_name = session.get('model_name', 'ERROR_ERROR')
            )

        # This needs to be able to change.
        if 'kmt' in session:
            kmt = session.pop('kmt', None)
        else:
            kmt = KerasModelToggle(model=session['keras_model'],
                                    user_features=session['fg__user_features'],
                                    user_price=session['user_provided_price'],
                                    user_home_formatted=session['fg__user_home_formatted'])

        # At this point, the first run, user_features_mod is just the user defined stuff.
        user_form = generate_user_parameters(kmt.user_features_mod)
        return render_template('toggle_model.html', UserHomeForm = user_form)
    if request.method == "POST":
        # The user has submitted a new optimization.
        if request.form.get('submit') or '' == 'Submit':
            toggle = {}
            toggle['beds'] = request.form.get('beds') or kmt.fg.user_features.get('beds')
            toggle['baths_full'] = request.form.get('baths_full') or kmt.fg.user_features.get('baths_full')
            toggle['three_qtr_baths'] = request.form.get('baths_3qtr') or kmt.fg.user_features.get('baths_full')
            toggle['half_baths'] = request.form.get('baths_half') or kmt.fg.user_features.get('baths_full')
            toggle['qtr_bath'] = request.form.get('baths_1qtr') or kmt.fg.user_features.get('baths_full')
            toggle['garage'] = True if request.form.get('garage') or 0 > 0 else False
            kmt.modify_attributes(**toggle)

            print('wow, made it here.')
            print(kmt.get_current_user_house_attributes())
            print(kmt.get_proposed_user_house_attributes())

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