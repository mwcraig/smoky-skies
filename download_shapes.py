from datetime import date, timedelta
from pathlib import Path
from argparse import ArgumentParser
import requests
from zipfile import ZipFile


BASE_URL = ('https://satepsanone.nesdis.noaa.gov'
            '/pub/FIRE/web/HMS/Smoke_Polygons/Shapefile/')

sample_url = '2023/05/hms_smoke20230501.zip'


def get_one_file(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        return None


def url_from_date(a_date):
    return (BASE_URL +
            f'{a_date.year}/{a_date.month:02}/hms_smoke{a_date.strftime("%Y%m%d")}.zip')


def download_and_unzip(a_date):
    final_path = Path(f'smoke_extents/{a_date.strftime("%Y%m%d")}')
    if final_path.exists():
        print(f"Data for {a_date.strftime("%Y%m%d")} already downloaded, skipping")
        return
        
    url = url_from_date(a_date)
    print(f'Getting {url}')
    content = get_one_file(url)

    if content:
        zipfile = Path(f'smoke_extents/{a_date.strftime("%Y%m%d")}.zip')
        with open(zipfile, 'wb') as f:
            f.write(content)
    else:
        zipfile = ''
        print(f'No content for {url}')

    if zipfile:
        with ZipFile(zipfile, 'r') as zip_ref:
            zip_ref.extractall(f'smoke_extents/{a_date.strftime("%Y%m%d")}')
        zipfile.unlink()


def main(start_date):
    smoke_dir = Path("smoke_extents")
    smoke_dir.mkdir(parents=True, exist_ok=True)
    delta = timedelta(days=1)
    next_date = start_date
    while next_date <= date.today():
        download_and_unzip(next_date)
        next_date += delta

if __name__ == "__main__":
    main(date(2024, 1, 6))