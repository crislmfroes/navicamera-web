from wtforms import Form, StringField, validators

class LoginForm(Form):
    login = StringField('Login', [validators.InputRequired()])
    senha = StringField('Senha', [validators.InputRequired(), validators.Length(min=8)])

class CadastroForm(LoginForm):
    confirmaSenha = StringField('Confirmar senha', [validators.EqualTo('senha')])