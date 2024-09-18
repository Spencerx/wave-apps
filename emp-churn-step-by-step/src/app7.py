# Step 7
# Add Employee details table below Stats Card
# ---
from h2o_wave import main, app, Q, ui, on, run_on, data

import altair
import numpy as np
import pandas as pd
import os


@app('/')
async def serve(q: Q):
    # First time the app is loaded
    if not q.app.initialized:
        await init_app(q)
        q.app.initialized = True

    # First time a browser comes to the app
    if not q.client.initialized:
        await init(q)
        q.client.initialized = True

    # Other browser interactions
    await run_on(q)
    await q.page.save()


async def init_app(q: Q) -> None:
    # Read and load data into memory
    file_path = os.path.abspath(__file__)
    dir_path = os.path.dirname(file_path)
    predictions_file = os.path.join(dir_path, 'static', 'predictions.csv')
    shapley_file = os.path.join(dir_path, 'static', 'shapley_values.csv')
    q.app.predictions = pd.read_csv(predictions_file)
    q.app.predictions = q.app.predictions.rename(columns={'Attrition.Yes': "Prediction"})
    q.app.shapley = pd.read_csv(shapley_file)


async def init(q: Q) -> None:
    q.client.cards = set()
    q.client.dark_mode = False

    q.page['meta'] = ui.meta_card(
        box='',
        title='Employee Churn Prediction',
        layouts=[
            ui.layout(
                breakpoint='xs',
                min_height='100vh',
                max_width='1200px',
                zones=[
                    ui.zone('header'),
                    ui.zone('content', size='1', zones=[
                        ui.zone('horizontal', direction=ui.ZoneDirection.ROW),
                        ui.zone('vertical', size='1', )
                    ]),
                    ui.zone(name='footer'),
                ]
            )
        ]
    )
    q.page['header'] = ui.header_card(
        box='header',
        title='Employee Churn Prediction',
        subtitle="Predict which employees are at risk and identify relevant factors."
    )
    q.page['footer'] = ui.footer_card(
        box='footer',
        caption='Made with 💛 using [H2O Wave](https://wave.h2o.ai).'
    )

    q.client.threshold = 0.5

    await home(q)


@on()
async def home(q: Q):
    clear_cards(q)

    # Distribution of prediction
    spec = altair.Chart(q.app.predictions).mark_bar().encode(
        altair.X("Prediction", bin=True),
        y='count()',
    ).properties(width='container', height='container').interactive().to_json()

    add_card(q, 'predictions_card', ui.vega_card(box='horizontal', title='Churn Predictions',
        specification=spec
    ))

    # Variable importance graph
    varimp = get_varimp(q.app.shapley)

    add_card(q, 'varimp_card', ui.plot_card(box='horizontal', title='Top Factors Affecting Churn',
        data=data('feature importance', 5, rows=varimp),
        plot=ui.plot([ui.mark(type='interval', x='=importance', y='=feature', x_min=0, color='#9c3a3a')])
    ))

    # Statistics by Threshold
    threshold = q.client.threshold if q.args.threshold is None else q.args.threshold

    add_card(q, 'description_card', ui.form_card(box='vertical', items=[
        ui.text("Use the slider below to change the cutoff for churn prediction and update the statistics.")
        ]
    ))

    add_card(q, 'threshold_card', ui.form_card(box='vertical', items=[
        ui.slider(name='threshold', label='Prediction Threshold', 
            min=0, max=0.9, step=0.1, value=threshold, trigger=True)
        ]
    ))

    churned_employees = q.app.predictions[q.app.predictions['Prediction'] > threshold]

    add_card(q, 'stats_card', ui.form_card(box='vertical', items=[
        ui.stats([
            ui.stat(label='Number of Employees', value=str(len(churned_employees)), caption='Predicted Churn Employees'),
            ui.stat(label='% of Employees', value="{0:.0%}".format(len(churned_employees)/len(q.app.predictions)), caption='Predicted Churn Employees'),
            ui.stat(label='Average Years at the Company', value=str(round(churned_employees.YearsAtCompany.mean())), caption='Predicted Churn Employees'),
            ], justify='between')
        ]
    ))

    # Churned Employees Table
    cols= ['EmployeeNumber'] + [i[0] for i in varimp] + ["Prediction"]
    add_card(q, 'table_card', ui.form_card(box='vertical', items=[
        ui.table(
        name='render_employee',
        columns=[ui.table_column(name=i, label=i, sortable=True) for i in cols], 
        rows=[ui.table_row(name=str(row['EmployeeNumber']),
                           cells=[str(k) for k in row[cols]]) for i, row in churned_employees.iterrows()]
    )]
    ))

@on()
async def threshold(q: Q):
    await home(q)

@on()
async def render_employee(q: Q):
    q['table_card'].items=[]
    await q.page.save()

def get_varimp(shapley_vals, top_n=5):
    varimp = shapley_vals[[i for i in shapley_vals.columns if 'contrib' in i and i != 'contrib_bias']]
    varimp = varimp.abs().mean().reset_index()
    varimp.columns = ["Feature", "Importance"]
    varimp['Feature'] = varimp['Feature'].str.replace("contrib_", "")
    varimp = varimp.sort_values(by="Importance", ascending=False).head(n=top_n)
    varimp = varimp.values.tolist()[::-1]
    
    return varimp


# Use for cards that should be deleted on calling `clear_cards`. Useful for routing and page updates.
def add_card(q, name, card) -> None:
    q.client.cards.add(name)
    q.page[name] = card


def clear_cards(q, ignore=[]) -> None:
    for name in q.client.cards.copy():
        if name not in ignore:
            del q.page[name]
            q.client.cards.remove(name)