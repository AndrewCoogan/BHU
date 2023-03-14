#type:ignore
from flask import Flask, render_template, request, url_for, redirect, session, flash
from flask_wtf import FlaskForm
from wtforms.fields import IntegerField, SubmitField, RadioField, DecimalField, TextAreaField
from wtforms.widgets import Input
from flask_bootstrap import Bootstrap5
import secrets
import os

from BHU import get_PropertyDetail, House
from BHU.KerasModelToggle import KerasModelToggle
from BHU.API_Calls import _flask_get_UserHome
from BHU.KerasTransformers import get_keras_pipeline_from_file

app = Flask(__name__)
app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = 'zephyr'
app.config['BOOTSTRAP_BTN_STYLE'] = 'primary'
app.config['BOOTSTRAP_BTN_SIZE'] = 'sm'
app.config['BOOTSTRAP_TABLE_VIEW_TITLE'] = 'Read'
app.config['BOOTSTRAP_TABLE_EDIT_TITLE'] = 'Update'
app.config['BOOTSTRAP_TABLE_DELETE_TITLE'] = 'Remove'
app.config['BOOTSTRAP_TABLE_NEW_TITLE'] = 'Create'
app.secret_key = secrets.token_hex()

bootstrap = Bootstrap5(app)

'''
GET : This method pulls specific information form the webserver (just to view it)
POST : This method sends data from the user to the server.

Instagram users scrolling are GETTING, when they post a photo, they POST.

I will need GET and POST in anything the user is submitting, like index.html.

select = SelectField(choices=[('dog', 'Dog'), ('cat', 'Cat'), ('bird', 'Bird'), ('alien', 'Alien')])

When we get further, we should have a start over button, popping the variables and loading the main page.

On the main page--list caveats: single family, etc.

Bottom of Attributes, or the toggle page, pictures of the house, links should be around in the meta data..
'''

### JUST DO THIS IN PYTHON AND SEND A STRING!!!

class DollarField(TextAreaField):
    widget = Input()
    def _value(self):
        if self.data:
            return "${:.2f}".format(float(self.data))

class ButtonForm(FlaskForm):
    submit = SubmitField()
    reset = SubmitField()
    cancel = SubmitField()

class DollarForm(FlaskForm):
    new_price = DollarField()
    dollar_delta = DollarField()
    pct_delta = DecimalField()

def generate_user_parameters(features, price_from_API = 0):
    class UserHomeForm(FlaskForm):
        year_built = IntegerField("Year Built")
        sqft = IntegerField("Square Footage")
        lot_sqft = IntegerField("Lot Square Footage")
        beds = IntegerField("Beds")
        baths_full = IntegerField("Full Baths")
        baths_3qtr = IntegerField("3/4 Baths")
        half_baths = IntegerField("1/2 Baths")
        baths_1qtr = IntegerField("1/4 Baths")
        garage = RadioField("Garage?", choices=[('yes', 'Yes'), ('no', 'No')])
        new_construction = RadioField("New Construction?",choices=[('yes', 'Yes'), ('no', 'No')])
        price = IntegerField("Price")
        submit = SubmitField()
        reset = SubmitField()
        cancel = SubmitField()

    uhf = UserHomeForm()
    uhf.year_built.default = features.get('year_built', 0)
    uhf.sqft.default = features.get('sqft', 0)
    uhf.lot_sqft.default = features.get('lot_sqft', 0)
    uhf.beds.default = features.get('beds', 0)
    uhf.baths_full.default = features.get('baths_full', 0)
    uhf.baths_3qtr.default = features.get('baths_3qtr', 0)
    uhf.half_baths.default = features.get('baths_half', 0)
    uhf.baths_1qtr.default = features.get('baths_1qtr', 0)
    uhf.garage.default = 'yes' if features.get('garage', 0) > 0 else 'no'
    uhf.new_construction.default = 'yes' if features.get('new_construction') else 'no'
    uhf.price.default = price_from_API
    uhf.process()
    return uhf

def valid_location(session = session):
    city = session.get('user_home', {}).get('city') or ''
    state = session.get('user_home', {}).get('state_code') or ''
    model_code = f'{city.upper()}_{state.upper()}'
    model_location = 'BHU/Saved Results/KerasModel/'
    available_models = os.listdir(model_location)
    return (True if model_code + '.pkl' in available_models else False, city, state)

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
            # If we are here, we know it was an ambiguous address.
            multiple_addresses = [a['full_address'][0] for a in user_home]
            session['addresses'] = multiple_addresses
            return redirect(url_for('choose_address'))
    return render_template('index.html')

@app.route('/choose/', methods=['GET', 'POST'])
def choose_address():
    if request.method == 'POST':
        if request.form['submit_button'] == 'submit-address':
            session.pop('addresses', None)
            selected_address = request.form.get("options")
            # If the user selects none, go back to home page.
            if selected_address == 'none':
                session.clear()
                return redirect(url_for('main_page'))
            session['user_home'] = _flask_get_UserHome(selected_address)
            # Is the city covered by BHU?
            user_choice_valid, city, state = valid_location()
            # If not, throw an error and go back to the home page.
            if not user_choice_valid:
                flash(f'Unfortunately, there is no working model currently available for {city}, {state}.', 'warning')
                session.clear()
                return redirect(url_for('main_page'))
            # If yes, lets load the models and proceed.
            session['model_name'] = f'{city.upper()}_{state.upper()}'
            return redirect(url_for('verify_address_attributes'))
    return render_template('choose.html')

@app.route('/attributes/', methods=['GET', 'POST'])
def verify_address_attributes():
    if request.method == 'GET':
        user_home_details = get_PropertyDetail(session.get('user_home', {}).get('property_id'))
        user_house = House(user_home_details, user_house=True)
        user_form = generate_user_parameters(user_house.user_house_features(), user_house.house_price())

        session['user_home_features'] = user_house.user_house_features()
        session['user_home_price'] = user_house.house_price()
        session['user_home_address'] = user_house.address
        session['model_name'] = f'{user_house.city}_{user_house.state}'

        # address - user_house.address

        ### I am going to remove the loading of features to save space. 
        ### I will no longer need to feed that into KerasModel
        # session['fg__features'] = fg.features
        # session['fg__targets'] = fg.targets
        return render_template('attributes.html', UserHomeForm = user_form, ButtonForm = ButtonForm())
    elif request.method == 'POST':
        # Here we need to read in the users values and update them. We should assume we need to update them all.
        if request.form.get('submit') == 'Submit':
            # I need to pull in all of the info from the web form.
            user_features = session.pop('user_home_features', None)
            user_features['year_built'] = int(request.form.get('year_built', 0))
            user_features['sqft'] = int(request.form.get('sqft', 0))
            user_features['lot_sqft'] = int(request.form.get('lot_sqft', 0))
            user_features['beds'] = int(request.form.get('beds', 1))
            user_features['baths_full'] = int(request.form.get('baths_full', 0))
            user_features['baths_3qtr'] = int(request.form.get('baths_3qtr', 0))
            user_features['baths_half'] = int(request.form.get('baths_half', 0))
            user_features['baths_1qtr'] = int(request.form.get('baths_1qtr', 0))
            user_features['garage'] = True if request.form.get('garage') or 0 > 0 else False
            user_features['new_construction'] = True if request.form.get('new_construction') else False
            session['user_home_features'] = user_features

            if 'user_provided_price' not in session:
                session['user_provided_price'] = request.form.get('price')

            return redirect(url_for('toggle_model'))
        if request.form.get('submit') == 'cancel':
            session.clear()
            flash(f'Cookies have been cleared.', 'success')
            return redirect(url_for('main_page'))
    flash(f'Something horribly wrong happened, sending you back to a safe place.', 'warning')
    return redirect(url_for('main_page'))

@app.route('/toggle/', methods=['GET', 'POST'])
def toggle_model():
    if request.method == "GET":
        # Keras Pipelines are Non-Serializable :(
        # This is going to have the same initialization, every time.
        
        if 'user_feature_mod' in session:
            # Here I only need to get two things, user_feature_mod and the price from the POST call 
            # So, is this where reset goes?           
            user_feature_mod = session.pop('user_feature_mod', None)
            user_form = generate_user_parameters(user_feature_mod)
            
            ### I NEED TO PULL IN THE DICT AND PARSE HERE, THATS FINE.
            price_stats = session.pop('price_stats', 0)
            session.pop('new_house_stats', None)
            session['new_house_stats'] = [price_stats]
        else:
            # I just need to show the original features here.
            user_form = generate_user_parameters(session['user_home_features'])
            ### I need to make a form for price and other stats, I can fill it in with default values here.
            ### PRICE, DOLLAR DELTA, PERCENT DELTA
            default_stats = {
                'scaled_new_value' : session.get('user_home_price', 0),
                'dollar_delta' : 0,
                'pct_delta' : 0
            }
            session['new_house_stats'] = [default_stats]

        # (internal id, public symbol)
        if 'titles' not in session:
            session['titles'] = [('scaled_new_value', 'Projected Price'),
                                 ('dollar_delta', 'Projected Delta ($)'), 
                                 ('pct_delta', 'Projected Delta (%)')]

        # At this point, the first run, user_features_mod is just the user defined stuff.
        return render_template('toggle_model.html', 
                               UserHomeForm = user_form, 
                               ButtonForm = ButtonForm(),
                               New_House_Stats = session['new_house_stats'],
                               Titles = session['titles'],
                               user_provided_price = session['user_home_price'])
    if request.method == "POST":
        # The user has submitted a new optimization.

        if request.form.get('submit') == 'Reset':
            redirect(url_for('toggle_model'))
        elif request.form.get('submit') == 'Cancel':
            session.clear()
            flash('All cookies have been cleared. Play again!', 'success')
            redirect(url_for('main_page'))
        elif request.form.get('submit') == 'Submit':
            # I can save the output here in the cookie and feed it into the GET
            keras_model_toggle = KerasModelToggle(get_keras_pipeline_from_file(session['model_name']),
                                                  user_features=session['user_home_features'],
                                                  user_price=session['user_home_price'],
                                                  address=session['user_home_address'])
            # ^^^^ I need to initialize this here every time.

            toggle = {}
            toggle['beds'] = request.form.get('beds') or kmt.fg.user_features.get('beds')
            toggle['baths_full'] = request.form.get('baths_full', 0)
            toggle['baths_3qtr'] = request.form.get('baths_3qtr', 0)
            toggle['baths_half'] = request.form.get('baths_half', 0)
            toggle['baths_1qtr'] = request.form.get('baths_1qtr', 0)
            toggle['garage'] = True if request.form.get('garage') or 0 > 0 else False

            keras_model_toggle.modify_attributes(**toggle)
            new_values = keras_model_toggle.predit_new_value()
            session.pop('new_house_stats', None)
            session['new_house_stats'] = [new_values]
            user_form = generate_user_parameters(keras_model_toggle.user_features_mod)
            return render_template('toggle_model.html',
                                   UserHomeForm = user_form,
                                   ButtonForm = ButtonForm(),
                                   New_House_Stats = session['new_house_stats'],
                                   Titles = session['titles'],
                                   user_provided_price = session['user_home_price'])

    pass

@app.route('/about/', methods=['GET', 'POST'])
def about_form():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)