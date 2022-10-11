import functools
import random
import flask
from . import utils

from email.message import EmailMessage
import smtplib

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db #Captura DB 

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/activate', methods=('GET', 'POST')) #Usa ambos metodos
def activate():
    try:
        if g.user: #Si el usuario esta logged, colocarlo en la vista show.html para que vea msj
            return redirect(url_for('inbox.show'))
        
        if request.method == 'GET': #Para leer desde el navegador
            number = request.args['auth'] #Almacena el challenge (codigo e-mail)
            
            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            attempt = db.execute(
                'SELECT * FROM activationlink WHERE challenge=? AND state=?', (number, utils.U_UNCONFIRMED)
            ).fetchone() #Compara o busca en la tabla el codigo del e-mail con challenge y con estado sin confirmar

        
            if attempt is not None: #Valida que el resultado no este vacio
                db.execute(
                    'UPDATE activationlink SET state=? WHERE id=?', (utils.U_CONFIRMED, attempt['id'])
                ) #Actualiza el registro del usuario cambiando su estado de no confirmado a confirmado
                db.execute(
                    'INSERT INTO user (username, password, salt, email) VALUES (?,?,?,?)', 
                    (attempt['username'], attempt['password'], attempt['salt'], attempt['email'])
                )
                db.commit()#Inserta los datos del usuario registrado en la tabla del user

        return redirect(url_for('auth.login')) #Retorna al usuario a la vista login.html
    except Exception as e:
        print(e)
        return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET','POST'])
def register():
    try:
        if g.user: #Si el usuario esta logged, colocarlo en la vista show.html para que vea msj
            return redirect(url_for('inbox.show'))
      
        if request.method == 'POST': #El fomulario de register.html tiene metodo post para seguridad de los datos   
            username =request.form['username'] #Asigna datos desde formularios register.html
            password = request.form['password']
            email = request.form['email']
            
            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            error = None
            #Inicia bloque de comprobacion o validacion de los datos de usuario
            if not username: #Valida si no hay usuario
                error = 'El nombre de usuario es requerido.'
                flash(error)
                return render_template('auth/register.html') #Envia al usuario a la vista register.html
            
            if not utils.isUsernameValid(username): #Valida si no cumple las conciones del username
                error = "El nombre de usuario tiene que ser alfanumerico mas '.','_','-'"
                flash(error)
                return render_template('auth/register.html')

            if not utils.isPasswordValid(password): #Valida si no cumple las conciones del password
                error = 'La contraseña es requerida.'
                flash(error)
                return render_template('auth/register.html')

            if db.execute('SELECT username FROM user WHERE username=?', (username,)).fetchone() is not None: #Valida si el usuario esta registrado, Si el resultado no en nulo dispara error
                error = 'El usuario {} ya se encuentra registrado.'.format(username)
                flash(error)
                return render_template('auth/register.html')
            
            if (not email or (not utils.isEmailValid(email))): #Valida si el e-mail no es valido
                error =  'La dirección de correo electronica es invalida.'
                flash(error)
                return render_template('auth/register.html')
            
            if db.execute('SELECT email FROM user WHERE email=?', (email,)).fetchone() is not None: #Valida que el e-mail esta registrado, Si el resultado no en nulo dispara error
                error =  'Email {} Esta ya registrado.'.format(email)
                flash(error)
                return render_template('auth/register.html')
            
            if (not utils.isPasswordValid(password)): #Valida que el password no cumple las condiciones minimas
                error = 'Su contraseña debe tener al menos una minuscula, una mayuscula y un numero con 8 caracteres'
                flash(error)
                return render_template('auth/register.html')

            salt = hex(random.getrandbits(128))[2:] #Encripta el password generando un numero aleatorio y conbinandolo con este
            hashP = generate_password_hash(password + salt)
            number = hex(random.getrandbits(512))[2:] #challenge

            db.execute(
                'INSERT INTO activationlink (challenge, state, username, password, salt, email) VALUES (?,?,?,?,?,?)',
                (number, utils.U_UNCONFIRMED, username, hashP, salt, email)
            )
            db.commit() #Registro usuario a la DB activationlink

            credentials = db.execute( #Validacion de credenciales del e-mail del emisor del link de activacion (line 55 schema.sql)
                'SELECT user,password FROM credentials WHERE name=?', (utils.EMAIL_APP,)
            ).fetchone()

            content = 'Hola, para la activacion de su cuenta, por favor click en el siguiente enlace ' + flask.url_for('auth.activate', _external=True) + '?auth=' + number
            
            send_email(credentials, receiver=email, subject='Active su cuenta', message=content) #Envia el mensaje de activacion al e-mail
            
            flash('Por favor, revisar en tu e-mail registrado para la activacion de su cuenta')
            return render_template('auth/login.html') #Ubica al usuario en la vista login.html

        return render_template('auth/register.html') #Ubica al usuario en la vista register.html
    except:
        return render_template('auth/register.html')

    
@bp.route('/confirm', methods=['GET','POST'])
def confirm():
    try:
        if g.user: #Si el usuario esta logged, colocarlo en la vista show.html para que vea msj
            return redirect(url_for('inbox.show'))

        if request.method =='POST': #SI: El fomulario de change.html tiene metodo post para seguridad de los datos 
            password = request.form['password'] #Asigna datos desde formularios change.html
            password1 = request.form['password1']
            authid = request.form['authid'] #Numero alaeatorio que se envia al correo

            if not authid: #Valida si no existe el valor
                flash('Invalido')
                return render_template('auth/forgot.html') #Ubica al usuario en la vista forgot.html

            if not password: #Valida si password no tiene algun valor
                flash('Contraseña requerida')
                return render_template('auth/change.html', number=authid) #Ubica al usuario en la vista change.html

            if not password1: #Valida si password1 no tiene algun valor
                flash('Contraseña de  confirmacion requerida')
                return render_template('auth/change.html', number=authid) #Ubica al usuario en la vista change.html

            if password1 != password: #Valida si los pass son diferentes
                flash('Ambas contraseñas deben ser iguales')
                return render_template('auth/change.html', number=authid) #Ubica al usuario en la vista change.html

            if not utils.isPasswordValid(password): #Valida si el password es invalido
                error = 'Su contraseña debe tener al menos una minuscula, una mayuscula y un numero con 8 caracteres'
                flash(error)
                return render_template('auth/change.html', number=authid) #Ubica al usuario en la vista change.html

            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            attempt = db.execute(
                'SELECT * FROM forgotlink WHERE challenge=? AND state=?', (authid, utils.F_ACTIVE)
            ).fetchone() #Consulta a la tabla forgotlink para challenge y estado activo
            
            if attempt is not None: #Si la consulta tiene un resultado
                db.execute(
                    'UPDATE forgotlink SET state=? WHERE id=?', (utils.F_INACTIVE, attempt['id'])
                ) #Si el registro existe, sobreescribe el estado de activo a inactivo
                salt = hex(random.getrandbits(128))[2:]
                hashP = generate_password_hash(password + salt)   
                db.execute(
                    'UPDATE user SET password=?, salt=? WHERE id=?', (hashP, salt, attempt['userid'])
                ) #Se actualiza el nuevo password del usuario en la tabla user (salt cambia cada vez que cambia el password)
                db.commit()
                return redirect(url_for('auth.login')) #Ubica al usuario en la vista login.html
            else:
                flash('Invalido')
                return render_template('auth/forgot.html') #Ubica al usuario en la vista forgot.html

        return render_template('auth/forgot.html')
    except:
        return render_template('auth/forgot.html')


@bp.route('/change', methods=('GET', 'POST'))
def change():
    try:
        if g.user: #Si el usuario esta logged, colocarlo en la vista show.html para que vea msj
            return redirect(url_for('inbox.show'))
        
        if request.method == 'GET': #Para leer del correo
            number = request.args['auth'] #Recibe desde el link de olvido o cambio de contraseña del correo la variable auth
            
            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            attempt = db.execute(
                'SELECT * FROM forgotlink WHERE challenge=? AND state=?', (number, utils.F_ACTIVE)
            ).fetchone() #Consulta a la tabla de linkforgot para comparar auth vs challenge y valida estado activo
            
            if attempt is not None: #Si la consulta trae resultado
                return render_template('auth/change.html', number=number) #Ubica al usuario en la vista change.html
        
        return render_template('auth/forgot.html') #Ubica al usuario en la vista forgot.html
    except:
        return render_template('auth/forgot.html')


@bp.route('/forgot', methods=('GET', 'POST'))
def forgot():
    try:
        if g.user: #Si el usuario esta logged, colocarlo en la vista show.html para que vea msj
            return redirect(url_for('inbox.show'))
        
        if request.method == 'POST': #SI: El fomulario de forgot.html tiene metodo post para seguridad de los datos 
            email = request.form['email'] #Asigna el e-mail desde formulario forgot.html
            
            if (not email or (not utils.isEmailValid(email))): #Si no existe e-mail o si no pasa la validacion de e-mail
                error = 'Direccion de correo electronico invalido'
                flash(error)
                return render_template('auth/forgot.html') #Ubica al usuario en la vista forgot.html

            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            user = db.execute(
                'SELECT * FROM user WHERE email=?', (email,)
            ).fetchone() #Consulta a la tabla user para localizar su e-mail

            if user is not None: #Si el resultado de la consulta no es vacia
                number = hex(random.getrandbits(512))[2:] #Genera un codigo
                
                db.execute(
                    'UPDATE forgotlink SET state=? WHERE userid=?',
                    (utils.F_INACTIVE, user['id'])
                ) #Actualiza en la tabla forgotlink el registro estado del usuario colocandolo inactivo
                db.execute(
                    'INSERT INTO forgotlink (userid,challenge,state) VALUES(?,?,?)',
                    (user['id'], number, utils.F_ACTIVE)
                )
                db.commit() #Inserta en la tabla forgotlink el Id, challenge y estado Activo de nuevo
                
                credentials = db.execute(
                    'SELECT user,password FROM credentials WHERE name=?',(utils.EMAIL_APP,)
                ).fetchone() #Consulta la tabla credentials para el usuario
                #Genera el mensaje de cambio de contraseña y el enlace
                content = 'Hola, para cambiar contraseña, por favor click en el siguiente enlace ' + flask.url_for('auth.change', _external=True) + '?auth=' + number
                
                send_email(credentials, receiver=email, subject='Cambio de Contraseña!', message=content) #Envia e-mail de cambio de contraseña
                
                flash('Por favor verificar en su e-mail que registro en el sistema')
            else:
                error = 'El correo electronico no esta registrado'
                flash(error)            
        return render_template('auth/forgot.html') #Ubica al usuario en la vista #forgot.html
    except:
        return render_template('auth/forgot.html')


@bp.route('/login', methods=['GET','POST'])
def login():
    try:
        if g.user: #Si el usuario esta logged, colocarlo en la vista show.html para que vea msj
            return redirect(url_for('inbox.show'))

        if  request.method == 'POST': #SI: El fomulario de login.html tiene metodo post para seguridad de los datos
            username = request.form['username'] #Asigna datos desde formulario login.html
            password =request.form['password']

            if not username : #Valida si el usuario esta vacio
                error = 'El campo de usuario es requerido'
                flash(error)
                return render_template('auth/login.html')

            if not password : #Valida si el password esta vacio
                error = 'El campo de la contraseña es requerido'
                flash(error)
                return render_template('auth/login.html')

            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            error = None
            user = db.execute(
                'SELECT*FROM user WHERE username=?', (username,)
            ).fetchone() #Consulta si el usuario existe en la tabla user
            print(username)
            print(user['username'])
            
            if username != user['username']: #Valida si los usuarios son diferentes o si el password es invalido
                error = 'Usuario incorrecto'
            elif not check_password_hash(user['password'], password + user['salt']):
                error = 'Contraseña incorrecta'   

            if error is None: #Valida si no se ha generado errores
                session.clear() #Limpia la sesion
                session['user_id'] = user['id'] #user_id es la variable de sesion (Inicia sesion el id del usuario)
                return redirect(url_for('inbox.show')) #Ubica la usuario en el inbox

            flash(error)

        return render_template('auth/login.html') #Ubica la usuario en la vista login.html
    except:
        return render_template('auth/login.html')
        

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id') #user_id es la variable de sesion (contiene id del usuario)

    if user_id is None: #Si no hay sesion
        g.user = None #No hay usuario logged
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id=?', (user_id,)
        ).fetchone() #Consulta a la tabla user para localizar el ID del usuario

        
@bp.route('/logout')
def logout():
    session.clear() #Cerrar la sesion
    return redirect(url_for('auth.login')) #Ubica al usuario en la vista login.html


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None: #Si no hay usuario logged
            return redirect(url_for('auth.login')) #Ubica al usuario en la vista login.html
        return view(**kwargs)
    return wrapped_view


def send_email(credentials, receiver, subject, message): #Funcion generar e-mail
    # Create e-mail
    email = EmailMessage()
    email["From"] = credentials['user']
    email["To"] = receiver
    email["Subject"] = subject
    email.set_content(message)

    # Send e-mail (Funcion para enviar e-mail)
    smtp = smtplib.SMTP("smtp-mail.outlook.com", port=587)
    smtp.starttls()
    smtp.login(credentials['user'], credentials['password'])
    smtp.sendmail(credentials['user'], receiver, email.as_string())
    smtp.quit()