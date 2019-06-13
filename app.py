import os
import pickle
import sys

import cv2
from cv2 import aruco
from flask import Flask, flash, redirect, render_template, request, url_for, session
from flask_sqlalchemy import SQLAlchemy

from threading import Timer

from sqlalchemy_utils.types.password import PasswordType, Password

from sqlalchemy_utils import force_auto_coercion

from flask_weasyprint import HTML, render_pdf

from flask_restful import Resource, Api

from forms.marcador import MarcadorForm

from forms.usuario import LoginForm, CadastroForm

from hashlib import md5

force_auto_coercion()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://{}:{}@navicamera".format(os.environ.get('DB_USER'), os.environ.get('DB_PASSWORD'))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

N_MARKERS = 1000
RANDOM_SEED = 123

base_dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_1000)
dictionary = aruco.custom_dictionary_from(1000, 5, base_dictionary, RANDOM_SEED)

db = SQLAlchemy(app)

api = Api(app)

class Marcador(db.Model):
    cod = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100))
    nome = db.Column(db.String(50))
    used = db.Column(db.Boolean)

class Usuario(db.Model):
    cod = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50))
    senha = db.Column(db.String(500))
    admin = db.Column(db.Boolean)

class ApiMarcadorAll(Resource):
    def get(self):
        marcadores = list()
        for marcador in Marcador.query.filter(Marcador.used == True).all():
            marcadores.append({
                'cod': marcador.cod,
                'nome': marcador.nome,
                'descricao': marcador.descricao
            })
        return marcadores

def delete_image(cod):
    if os.path.isfile(os.path.join('static', 'markers', '{}.png'.format(cod))):
        os.remove(os.path.join('static', 'markers', '{}.png'.format(cod)))

api.add_resource(ApiMarcadorAll, '/api/marcadores')

@app.before_first_request
def populate_database():
    if len(Marcador.query.all()) == 0:
        for i in range(1, N_MARKERS + 1):
            marcador = Marcador(cod=i, used=False)
            db.session.add(marcador)
        db.session.commit()
    try:
        os.mkdir(os.path.join('static', 'markers'))
    except FileExistsError:
        print('Encontrado diretório de marcadores ...')

@app.before_request
def filtra_login():
    if session.get('logado') != True and request.endpoint not in ['login', 'cadastro']:
        flash("Você precisa fazer login para ter acesso a esta parte do site.")
        return redirect(url_for('login'))

@app.route('/')
def listar():
    objetos = Marcador.query.filter(Marcador.used == True).all()
    return render_template('listar.html', objetos=objetos)

@app.route('/salvar', methods=['GET', 'POST'])
def salvar():
    form = MarcadorForm(request.form)
    cod = request.args.get('cod')
    if cod == None:
        marcador = Marcador.query.filter(Marcador.used == False).first()
    else:
        marcador = Marcador.query.filter(Marcador.cod == cod).first()
    if request.method == 'POST':
        marcador.nome = form.nome.data
        marcador.descricao = form.descricao.data
        marcador.used = True
        db.session.commit()
        return redirect(url_for('listar'))
    return render_template('formulario.html', form=form, marcador=marcador)

@app.route('/excluir')
def excluir():
    cod = request.args.get('cod')
    marcador = Marcador.query.filter(Marcador.cod == cod).first()
    marcador.nome = None
    marcador.descricao = None
    marcador.used = False
    db.session.commit()
    return redirect(url_for('listar'))

@app.route('/marcador')
def marcador():
    cod = request.args.get('cod')
    img_marcador = aruco.drawMarker(dictionary, int(cod) - 1, 600)
    cv2.imwrite(os.path.join('static', 'markers', '{}.png'.format(cod)), img_marcador)
    html = render_template('marcador.html', cod=int(cod))
    Timer(60, delete_image, (cod,)).start()
    return html

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST':
        login = form.login.data
        senha = md5(form.senha.data.encode('utf-8')).hexdigest()
        usuario = Usuario.query.filter_by(login=login, senha=senha).first()
        if usuario is not None:
            session['login'] = usuario.login
            session['admin'] = usuario.admin
            session['logado'] = True
            return redirect(url_for('listar'))
        return redirect(url_for('login'))
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    form = CadastroForm(request.form)
    if request.method == 'POST':
        usuario = Usuario()
        usuario.login = form.login.data
        usuario.senha = md5(form.senha.data.encode('utf-8')).hexdigest()
        usuario.admin = False
        db.session.add(usuario)
        db.session.commit()
        flash("Cadastro realizado com sucesso!")
        return redirect(url_for('login'))
    return render_template('cadastro.html', form=form)

def main():
    app.secret_key = os.environ.get('SECRET_KEY')
    if len(sys.argv) == 2:
        if sys.argv[1] == 'development':
            app.env = 'development'
            app.run(debug=True)
        elif sys.argv[1] == 'production':
            app.env = 'production'
            app.run(debug=False)
    app.env = 'production'
    app.run(debug=False)

if __name__ == '__main__':
    main()