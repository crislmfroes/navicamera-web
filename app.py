import os
import pickle
import sys
from genericpath import isfile
from hashlib import md5
from threading import Timer

import cv2
from cv2 import aruco
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from flask.json import jsonify
from flask_heroku import Heroku
from flask_sqlalchemy import SQLAlchemy

from forms.marcador import MarcadorForm
from forms.usuario import CadastroForm, LoginForm

app = Flask(__name__)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
heroku = Heroku(app)

N_MARKERS = 1000
RANDOM_SEED = 123

'''base_dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_1000)
dictionary = aruco.custom_dictionary_from(1000, 5, base_dictionary, RANDOM_SEED)
store = dictionary.bytesList'''

def get_dictionary():
    path = os.path.join('assets', 'dictByteList.json')
    try:
        if not os.path.isfile(path):
            raise FileNotFoundError()
        storage = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
        dictionary = aruco.custom_dictionary(1000, 5)
        dictionary.markerSize = int(storage.getNode("markerSize").real())
        dictionary.maxCorrectionBits = int(storage.getNode("maxCorrectionBits").real())
        dictionary.bytesList = storage.getNode("bytesList").mat()
        storage.release()
    except FileNotFoundError as e:
        storage = cv2.FileStorage(path, cv2.FILE_STORAGE_WRITE)
        dictionary = aruco.custom_dictionary(1000, 5)
        storage.write("markerSize", dictionary.markerSize)
        storage.write("maxCorrectionBits", dictionary.maxCorrectionBits)
        storage.write("bytesList", dictionary.bytesList)
        storage.release()
    return dictionary


dictionary = get_dictionary()
#dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_1000)

board = aruco.CharucoBoard_create(10, 10, 0.2, 0.16, dictionary)

app.secret_key = os.environ.get('SECRET_KEY')

db = SQLAlchemy(app)

class Marcador(db.Model):
    __tablename__ = "marcador"
    cod = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100))
    nome = db.Column(db.String(50))
    used = db.Column(db.Boolean)

class Usuario(db.Model):
    __tablename__ = "usuario"
    cod = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50))
    senha = db.Column(db.String(500))
    admin = db.Column(db.Boolean)


@app.route('/api/marcadores')
def get_marcadores():
    marcadores = list()
    for marcador in Marcador.query.filter(Marcador.used == True).all():
        marcadores.append({
            'cod': marcador.cod,
            'nome': marcador.nome,
            'descricao': marcador.descricao
        })
    return jsonify(marcadores)

def delete_image(cod):
    if os.path.isfile(os.path.join('static', 'markers', '{}.png'.format(cod))):
        os.remove(os.path.join('static', 'markers', '{}.png'.format(cod)))

#api.add_resource(ApiMarcadorAll, '/api/marcadores')

@app.before_first_request
def populate_database():
    try:
        db.create_all()
    except BaseException as e:
        print("Tabelas já inicializadas ...")
    if len(Marcador.query.all()) == 0:
        for i in range(1, N_MARKERS + 1):
            marcador = Marcador(cod=i, used=False)
            db.session.add(marcador)
        db.session.commit()
    try:
        os.mkdir(os.path.join('static', 'markers'))
    except FileExistsError:
        print('Encontrado diretório de marcadores ...')
    if Usuario.query.filter_by(admin=True).count() == 0:
        root = Usuario()
        root.admin = True
        root.login = os.environ.get('ROOT_LOGIN')
        root.senha = md5(os.environ.get('ROOT_PASSWORD').encode('utf-8')).hexdigest()
        db.session.add(root)
        db.session.commit()

@app.before_request
def filtra_login():
    if session.get('logado') != True and request.endpoint not in ['login', 'cadastro', 'get_marcadores']:
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
    if request.method == 'POST' and form.validate():
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

@app.route('/calibrar')
def calibrar():
    img_board = board.draw(outSize=(600, 600))
    cv2.imwrite(os.path.join('static', 'markers', 'board.png'), img_board)
    html = render_template('marcador.html', cod="board")
    Timer(60, delete_image, ("board",)).start()
    return html

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
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
    if request.method == 'POST' and form.validate():
        usuario = Usuario()
        usuario.login = form.login.data
        usuario.senha = md5(form.senha.data.encode('utf-8')).hexdigest()
        if Usuario.query.filter_by(login=usuario.login).count() == 0:
            usuario.admin = False
            db.session.add(usuario)
            db.session.commit()
            flash("Cadastro realizado com sucesso!")
            return redirect(url_for('login'))
        else:
            flash("Usuário já existe!")
            return redirect(url_for('cadastro'))
    return render_template('cadastro.html', form=form)

def main():
    port = os.environ.get('PORT')
    if len(sys.argv) == 2:
        if sys.argv[1] == 'development':
            app.env = 'development'
            app.run(debug=True, port=port)
        elif sys.argv[1] == 'production':
            app.env = 'production'
            app.run(debug=False, port=port)
    app.env = 'production'
    app.run(debug=False, port=port)

if __name__ == '__main__':
    main()