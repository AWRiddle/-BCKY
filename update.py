# -*- coding: utf-8 -*- 

import copy
import datetime
from dateutil import rrule, parser
from ftplib import FTP
from directoryelements import DirectoryElements
import json
import multiprocessing.dummy as mpd
import os
import pandas
from portfolios import Portfolios
import requests
import sys
import time



testing = True	# True for development and testing, False for production
poolsize = 8	# make my cpu cry!

NASDAQ_ftp = "ftp.nasdaqtrader.com"
NASDAQ_crosses_dir = "files/crosses"

credentials = "credentials"
IEX_baseurl = "https://cloud.iexapis.com/"
IEX_testurl = "https://sandbox.iexapis.com/"
get_stock = "/stock/"
get_previous = "/previous/"
query_parameters = {"chartByDay": "true"}	# this gets only the daily OHLCV data

symbol_column = u"symbol"
columns_to_remove = [
	u"label",
	u"date"
]

SPY = "SPY"

portfolios = Portfolios()
directory_elements = DirectoryElements()



def get_previous_trading_day():
	ftp = FTP(NASDAQ_ftp)
	ftp.login()
	ftp.cwd(NASDAQ_crosses_dir)
	previous_NASDAQ_trading_day = datetime.datetime.strptime(ftp.nlst()[-1], "CrossStats%Y%m%d.txt").date()

	trading_days_processed = [datetime.datetime.strptime(EOD, "%Y-%m-%d").date() for EOD in os.walk(directory_elements.EODs_dir).next()[-1]]

	return None if previous_NASDAQ_trading_day in trading_days_processed else previous_NASDAQ_trading_day



def get_credentials():
	with open(credentials, "r") as credentials_file:
		credentials_data = credentials_file.read()
		credentials_json = json.loads(credentials_data)

	tokens = credentials_json["tokens" if not testing else "test tokens"]

	token = str(tokens["publishable token"])
	if not token:
		token = str(tokens["secret token"])
		if not token:
			print >> stdout, "no tokens available"
			exit(1)

	return token



def query_thread(symbol):
	global EOD_ohlcv
	global BCKY_A_ohlcv
	global BCKY_B_ohlcv
	global BCKY_V_ohlcv

	symbol_ohlcv = json.loads(requests.get((IEX_baseurl if not testing else IEX_testurl) + get_stock + symbol + get_date_query, params = query_parameters).text)[0]
	for column in columns_to_remove:
		del symbol_ohlcv[column]
	symbol_ohlcv[symbol_column] = symbol

	EOD_ohlcv.append(symbol_ohlcv)
	if symbol in BCKY_A_symbols:
		BCKY_A_ohlcv.append(symbol_ohlcv)
	if symbol in BCKY_B_symbols:
		BCKY_B_ohlcv.append(symbol_ohlcv)
	if symbol in BCKY_V_symbols:
		BCKY_V_ohlcv.append(symbol_ohlcv)

	time.sleep(0.1)



def dict_to_DataFrame(BCKY_dict):
	BCKY_df = DataFrame(BCKY_dict)
	BCKY_df_columns = BCKY_df.columns.tolist()
	symbol_column_index = BCKY_df_columns.index(symbol_column)
	BCKY_df_columns = BCKY_df_columns[symbol_column_index:] + BCKY_df_columns[:BCKY_df_columns]
	BCKY_df = BCKY_df[BCKY_df_columns]
	BCKY_df.sort_values(by = symbol_column)
	return BCKY_df



def pd_to_csv(file_path, pd):
	if os.path.isfile(file_path):
		pd.to_csv(file_path, mode = 'a', header = False, index = False)
	else:
		pd.to_csv(file_path, index = False)


query_parameters["token"] = get_credentials()

BCKY_A_symbols = set(portfolios.BCKY_A.keys())
BCKY_B_symbols = set(portfolios.BCKY_B.keys())
BCKY_V_symbols = set(portfolios.BCKY_V.keys())
symbols = list(BCKY_A_symbols | BCKY_B_symbols | BCKY_V_symbols)

trading_day = get_previous_trading_day()
if trading_day:
	EOD_ohlcv = []
	BCKY_A_ohlcv = []
	BCKY_B_ohlcv = []
	BCKY_V_ohlcv = []

	if symbols:
		if __name__ == '__main__':
			trading_days_pool = mpd.Pool(poolsize)
			trading_days_pool.map(query_thread, symbols)
		trading_days_pool.join()

	EOD_df = dict_to_DataFrame(EOD_ohlcv)
	BCKY_A_df = dict_to_DataFrame(BCKY_A_ohlcv)
	BCKY_B_df = dict_to_DataFrame(BCKY_B_ohlcv)
	BCKY_V_df = dict_to_DataFrame(BCKY_V_ohlcv)
	pd_to_csv(os.path.join(directory_elements.EODs_dir, trading_day.isoformat()), EOD_df)
	pd_to_csv(os.path.join(directory_elements.BCKY_A_dir, trading_day.isoformat()), BCKY_A_df)
	pd_to_csv(os.path.join(directory_elements.BCKY_B_dir, trading_day.isoformat()), BCKY_B_df)
	pd_to_csv(os.path.join(directory_elements.BCKY_V_dir, trading_day.isoformat()), BCKY_V_df)

	SPY_ohlcv = json.loads(requests.get((IEX_baseurl if not testing else IEX_testurl) + get_stock + SPY + get_previous, params = query_parameters).text)[0]
	SPY_df = DataFrame(SPY)
	pd_to_csv(os.path.join(directory_elements.portfolios_dir, SPY), SPY_df)
	
	time.sleep(1)
