from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.sensors.http_sensor import HttpSensor
from airflow.models import Variable
from datetime import datetime, timedelta
import json
from airflow.providers.amazon.aws.operators.s3 import S3CreateObjectOperator
import pandas as pd
import requests

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 8, 12),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG('openweather_api_dag', default_args=default_args, schedule_interval="@once",catchup=False)

# Set your OpenWeather API endpoint and parameters
api_endpoint = "https://api.openweathermap.org/data/2.5/weather"
appid = Variable.get("key")
city_country = "Toronto,Canada"
api_params = {
        "q": "Toronto,Canada",
        "appid": Variable.get("key")
    }

def extract_openweather_data(**kwargs):
    print("Extracting started ")
    ti = kwargs['ti']
    response = requests.get(api_endpoint, params=api_params)
    data = response.json()
    print(data)
    df= pd.json_normalize(data)
    #df = pd.DataFrame(data['weather'])
    print(df)
    ti.xcom_push(key = 'final_data' , value = df.to_csv(index=False))
    
# Define the tasks
is_api_ready = HttpSensor(
    task_id='check_api_data',
    http_conn_id='http_weatherapi',
    endpoint= f'{api_endpoint}?q={city_country}&appid={appid}',
    response_check=lambda response: True if response.status_code == 200 else False,
    dag=dag,
)

extract_api_data = PythonOperator(
    task_id='extract_api_data',
    python_callable=extract_openweather_data,
    provide_context=True,
    dag=dag,
)

upload_to_s3 = S3CreateObjectOperator(
        task_id="upload_to_S3",
        aws_conn_id= 'AWS_CONN',
        s3_bucket='airflow-s3-bucket-datatech',
        s3_key='weather_api_data.csv',
        data="{{ ti.xcom_pull(key='final_data') }}",
        dag=dag,
    )

# Set task dependencies
is_api_ready >> extract_api_data >> upload_to_s3
