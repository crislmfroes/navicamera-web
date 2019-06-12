from wtforms import Form, StringField, validators

class LoginForm(Form):
    login = StringField('Login', [validators.InputRequired()])
    senha = StringField('Senha', [validators.InputRequired()])