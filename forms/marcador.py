from wtforms import Form, StringField, validators

class MarcadorForm(Form):
    nome = StringField('Nome', [validators.InputRequired()])
    descricao = StringField('Descrição', [validators.InputRequired()])