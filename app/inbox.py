from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app, send_file
)

from app.auth import login_required
from app.db import get_db

bp = Blueprint('inbox', __name__, url_prefix='/inbox')

@bp.route("/getDB") #Funcion para descargar al PC el archivo app.sql desde la vista show.html
@login_required
def getDB():
    return send_file(current_app.config['DATABASE'], as_attachment=True)


@bp.route('/show')
@login_required
def show():
    db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
    messages = db.execute(
        'SELECT * FROM message WHERE to_id=?', (g.user['id'],) #Consulta que filtra mensajes del usuario logged en el inbox
    ).fetchall()

    return render_template('inbox/show.html', messages=messages) #Ubica al usuario en la vista show.html


@bp.route('/send', methods=('GET', 'POST'))
@login_required
def send():
    if request.method == 'POST': #Recibe datos por formulario desde vista send.html       
        from_id = g.user['id'] 
        to_username = request.form['to'] #Asigna datos desde formularios vista.html
        subject =  request.form['subject']
        body = request.form['body']
        #print('************************************')
        print(from_id)
        print(to_username)
        print(subject)
        print(body)
        #print('****************************************')

        db =get_db() #Funcion para la Conexion a la DB (Desde db.py)
       
        if not to_username: #Valida si no hay usuario diligenciado
            flash('El campo es requerido')
            return render_template('inbox/send.html') #Ubica al usuario en la vista send.html
        
        if not subject: #Valida que no exista asunto del e-mail diligenciado
            flash('El asunto es requerido')
            return render_template('inbox/send.html')
        
        if not body: #Valida que el mensaje este vacio
            flash('Cuerpo del mensaje es requerido')
            return render_template('inbox/send.html')    
        
        error = None    
        userto = None 
        
        userto = db.execute(
            'SELECT * FROM user WHERE username=?', (to_username,)
        ).fetchone() #Localiza en la tabla user el nombre del usuario destino
        
        if userto is None: #Si no trae resultado de la consulta
            error = 'El destinatario no existe en el sistema'
     
        if error is not None: #Si error no está vacio
            flash(error)
        else:
            db = get_db() #Funcion para la Conexion a la DB (Desde db.py)
            db.execute(
                'INSERT INTO message (from_id,to_id,subject,body) VALUES(?,?,?,?)',
                (g.user['id'], userto['id'], subject, body)
            )
            db.commit() #Guarda en la tabla message la informacion del mensaje del usuario

            return redirect(url_for('inbox.show')) #Ubica al usuario en la vista show.html

    return render_template('inbox/send.html') #Ubica al usuario en la vista send.html