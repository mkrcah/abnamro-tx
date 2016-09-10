# coding=utf-8
from __future__ import print_function
import time
import os
import sys
import datetime
import tempfile
from shutil import copyfile

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import click

TARGET_DATA_FOLDER = '/data'
PAGE_TRANSITION_WAIT = 120  # seconds
DOWNLOAD_TIMEOUT = 20  # seconds


def eprint(*args, **kwargs):
    print("[ERROR]", *args, file=sys.stderr, **kwargs)


def iprint(*args, **kwargs):
    print("[INFO]", *args, **kwargs)
    sys.stdout.flush()


def init_chrome(download_folder):
    iprint("Starting chrome...")
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option('prefs', {
        'download.default_directory': download_folder,
        'download.prompt_for_download': False
    })

    d = webdriver.Chrome(chrome_options=chrome_options)
    d.implicitly_wait(PAGE_TRANSITION_WAIT)
    return d


def quit_chrome(d):
    iprint("Closing chrome")
    d.quit()


def click_on(d, xpath):
    iprint("Waiting for " + xpath)
    WebDriverWait(d, PAGE_TRANSITION_WAIT).until(
        EC.element_to_be_clickable((By.XPATH, xpath)))
    iprint("Clicking " + xpath)
    d.find_element_by_xpath(xpath).click()


def wait_for_download(dirname):
    iprint("Waiting for download to finish (by checking the download folder)")
    waiting_time = 0
    sleep_interval = 0.1
    def is_downloaded():
        return os.listdir(dirname) and os.listdir(dirname)[0].endswith(".TAB")
    while waiting_time < DOWNLOAD_TIMEOUT and not is_downloaded():
        time.sleep(sleep_interval)
        waiting_time += sleep_interval

    if waiting_time >= DOWNLOAD_TIMEOUT:
        eprint("Something went wrong, file download timed out")
        sys.exit(1)


def download_with_chrome(
        account_number, card_number, identification_code,
        period_from, period_to, filename):

    download_folder = tempfile.mkdtemp()
    d = init_chrome(download_folder)
    try:
        iprint("Loading login page")
        d.get("https://www.abnamro.nl/portalserver/en/personal/index.html")

        iprint("Accepting cookies")
        try:
            click_on(d, "//*[text()='Yes, I accept cookies']")
        except TimeoutException:
            iprint("Cookies window didn't pop up")

        iprint("Logging in")
        click_on(d, "//*[@title='Log in to Internet Banking']")
        click_on(d, "//*[@title='Log on with your identification code']/span")

        d.find_element_by_name('accountnumberInput').send_keys(account_number)
        d.find_element_by_name('cardnumberInput').send_keys(card_number)
        d.find_element_by_name('login-pincode-0').send_keys(identification_code)
        click_on(d, "//input[@type='submit']")

        iprint("We are in, navigation to the export page")
        try:
            click_on(d, "//*[text()='Yes, I accept cookies']")
        except TimeoutException:
            iprint("Cookies window didn't pop up")

        click_on(d, "//*[text()='Tools']")
        click_on(d, "//*[text()='Transactions']")

        iprint("Filling in export parameters")
        def fill_datepart(name, value):
            elem = d.find_element_by_name('mutationsDownloadSelectionCriteriaDTO.' + name)
            elem.clear()
            elem.send_keys(value)

        fill_datepart('bookDateFromDay', period_from.strftime('%d'))
        fill_datepart('bookDateFromMonth', period_from.strftime('%m'))
        fill_datepart('bookDateFromYear', period_from.strftime('%Y'))
        fill_datepart('bookDateToDay',  period_to.strftime('%d'))
        fill_datepart('bookDateToMonth', period_to.strftime('%m'))
        fill_datepart('bookDateToYear', period_to.strftime('%Y'))

        click_on(d, "//label[@for='periodType1']")

        fileformat = Select(d.find_element_by_name(
            'mutationsDownloadSelectionCriteriaDTO.fileFormat'))
        fileformat.select_by_visible_text('TXT')

        time.sleep(1)  # just to be sure, a lot of heavy JS is going on there
        click_on(d, "//*[text()='ok']")

        wait_for_download(download_folder)

        iprint("Copying downloaded file to the target directory")
        downloaded_filename = os.listdir(download_folder)[0]
        src_file = os.path.join(download_folder, downloaded_filename)
        dst_file = os.path.join(TARGET_DATA_FOLDER, filename or downloaded_filename)
        copyfile(src_file, dst_file)
        iprint("Done! Transaction file is located at " + dst_file)

    except:
        quit_chrome(d)
        raise

    quit_chrome(d)


def get_env_var(name):
    if name in os.environ:
        return os.environ[name]
    else:
        eprint("Environmental variable " + name + " not found")
        sys.exit(1)


def parse_date(s):
    try:
        return datetime.datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        eprint(s, "is not a date in YYYY-MM-DD format")
        sys.exit(1)


@click.command()
@click.option('--period-from', help='Date from, format YYYY-MM-DD', required=True)
@click.option('--period-to', help='Date to, format YYYY-MM-DD', required=True)
@click.option('--export-filename', help='Name of the downloaded CSV file')
def run(period_from, period_to, export_filename):
    """Download a list of transactions from AirBank"""
    download_with_chrome(
        account_number=get_env_var("ABNAMRO_ACCOUNT_NUMBER"),
        card_number=get_env_var("ABNAMRO_CARD_NUMBER"),
        identification_code=get_env_var("ABNAMRO_IDENTIFICATION_CODE"),
        period_from=parse_date(period_from),
        period_to=parse_date(period_to),
        filename=export_filename
    )


if __name__ == '__main__':
    run()
