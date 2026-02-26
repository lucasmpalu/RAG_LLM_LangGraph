from airflow import DAG 
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from get_data import check_new_pdfs, extract_new_pdfs

default_args = {
    'owner': 'lucas_palu',
    'start_date': datetime(2026, 2, 25),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    
}

with DAG('my_first_dag',
         default_args=default_args, 
         schedule_interval='@daily',     
         catchup=False):

    task1 = PythonOperator(
        task_id='identificar_nuevos_pdf',
        python_callable=check_new_pdfs 
    )

    task2 = PythonOperator(
        task_id='procesar_pdfs',
        python_callable=extract_new_pdfs,  
        op_kwargs={'index': 'my-first-rag'}  
    )



task1 >> task2

