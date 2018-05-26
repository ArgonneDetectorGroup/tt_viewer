from __future__ import division
import sys
print(sys.executable)

import os
import sqlite3
import flask
import zipfile
import numpy as np
import pandas as pd

#Set backend to one that doesn't require DISPLAY to be set
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

from io import BytesIO

app = flask.Flask(__name__)

#Try to load from local user config file
#If that doesn't exist, use the default
try:
    app.config.from_pyfile('config.py')
except IOError:
    app.config.from_pyfile('config_default.py')

#Locatio of database
DATABASE = app.config['DATABASE']

#Set the debug level
app.debug = app.config['DEBUG']

#The data repository is likely somewhere different between servers
DATA_PREFIX = app.config['DATAPATH_PREFIX']

def get_db():
    db = getattr(flask.g, '_database', None)
    if db is None:
        db = flask.g._database = sqlite3.connect(DATABASE)
    return db

@app.route('/')
def index():
    df = pd.read_sql_query("select * from TTData limit 0", get_db())

    df_head = df.columns.tolist()

    return flask.render_template('index.html', df_head = df_head)

@app.route('/get_json')
def get_json():
    df = pd.read_sql_query("select * from TTData order by wafer, subwafer, pixel", get_db())

    return df.to_json(orient='records')

@app.route('/download_file', methods=['GET', 'POST'])
def download_file():
    files_requested = flask.request.form.getlist('tt_plots')

    if len(files_requested) == 0:
        return index()
    else:
            
        fileTable = pd.read_sql_query("select * from DataFiles", get_db())

        file_locs = fileTable[fileTable['Name'].isin(files_requested)][['Name','Path']].values.tolist()

        memory_file = BytesIO()

        with zipfile.ZipFile(memory_file, 'w') as zf:
            for name, path in file_locs:
                zf.write(os.path.join(DATA_PREFIX, path), os.path.basename(path)+'_'+name.replace(':','-')+'.txt', zipfile.ZIP_DEFLATED)

        memory_file.seek(0)

        return flask.send_file(memory_file, attachment_filename='requested_data.zip', as_attachment=True)

@app.route('/static_plot', methods=['GET', 'POST'])
def gen_static_plot():
    plots_requested = flask.request.args.getlist('plots_requested')
    fileTable = pd.read_sql_query("select * from DataFiles", get_db())

    plot_locs = fileTable[fileTable['Name'].isin(plots_requested)][['Name','Path']].values.tolist()

    fig, ax = plt.subplots(1,1, figsize=(7,5))

    for name, path in plot_locs:
        plot_data = np.loadtxt(os.path.join(DATA_PREFIX, path), skiprows = 2)

        xs = plot_data[:,0]
        ys = plot_data[:,1]

        fname = os.path.basename(path)

        if '1ua' in fname:
            ys *= 1e6

        ax.plot(xs, ys, label=name+' - '+fname)

    leg = ax.legend(loc="upper left", title="sample - filename", bbox_to_anchor=[1.05, 1])

    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Resistance (Ohms)")

    output_stream = BytesIO()

    fig.savefig(output_stream, bbox_extra_artists=(leg,), bbox_inches='tight')

    output_stream.seek(0)
    return flask.send_file(output_stream, mimetype='image/png')

@app.route('/tt_plot', methods=['GET', 'POST'])
def show_plot():
    plots_requested = flask.request.form.getlist('tt_plots')

    if len(plots_requested) == 0:
        return index()
    else:
        return flask.render_template('show_plots.html',
                                plots_requested=plots_requested)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(flask.g, '_database', None)
    if db is not None:
        db.close()
