from __future__ import division

import os
import sqlite3
import flask
import numpy as np
import pandas as pd
import plotly as ply
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.figure
from matplotlib.figure import Figure
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

#Allow a custom path prefix for deploying into a subdirectory
#while using CGI on a server that won't let you edit the Apache
#configuration files
PATH_PREFIX = app.config['PREFIX']

#Make a wrapper that always passes the path_prefix to the templates
#so it makes calls a little cleaner
def render_template_prefix(template, **kwargs):
    return flask.render_template(template, path_prefix=PATH_PREFIX, **kwargs)

def get_db():
    db = getattr(flask.g, '_database', None)
    if db is None:
        db = flask.g._database = sqlite3.connect(DATABASE)
    return db

@app.route('/')
def index():
    df = pd.read_sql_query("select * from TTData limit 0", get_db())

    df_head = df.columns.tolist()

    return render_template_prefix('index.html', df_head = df_head)

@app.route('/get_json')
def get_json():
    df = pd.read_sql_query("select * from TTData order by wafer, subwafer, pixel", get_db())

    return df.to_json(orient='records')



@app.route('/static_plot', methods=['GET', 'POST'])
def gen_static_plot():
    plots_requested = flask.request.args.getlist('plots_requested')

    fileTable = pd.read_sql_query("select * from DataFiles", get_db())

    plot_locs = fileTable[fileTable['Name'].isin(plots_requested)][['Name','Path']].values.tolist()

    fig = Figure(figsize=(7,5))
    canvas = FigureCanvas(fig)

    ax = fig.add_subplot(111)

    for name, path in plot_locs:
        plot_data = np.loadtxt(path, skiprows = 2)

        xs = plot_data[:,0]
        ys = plot_data[:,1]

        fname = os.path.basename(path)

        if '1ua' in fname:
            ys *= 1e6

        ax.plot(xs, ys, label=name+' - '+fname)

    ax.legend(title="sample - filename")

    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Resistance (Ohms)")

    fig.tight_layout()

    fig.canvas.draw()

    output = BytesIO()
    # canvas.print_png(output)
    # response=flask.make_response(output.getvalue())
    # response.headers['Content-Type'] = 'image/png'

    fig.savefig(output)
    output.seek(0)
    return flask.send_file(output, mimetype='image/png')

    return response

@app.route('/tt_plot', methods=['GET', 'POST'])
def show_plot():
    plots_requested = flask.request.form.getlist('tt_plots')

    if len(plots_requested) == 0:
        return index()
    else:
        return render_template_prefix('show_plots.html',
                                plots_requested=plots_requested)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(flask.g, '_database', None)
    if db is not None:
        db.close()
