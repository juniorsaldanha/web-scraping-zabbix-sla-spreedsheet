import argparse, json, calendar
from zabbix_api import ZabbixAPI,logging
from time import sleep
from datetime import date, datetime, time
import pandas as pd


#Args to run this alg
parser = argparse.ArgumentParser()
parser.add_argument("--server", "-s",
    help="If u dont use http or https , the default option will be https://",
    default='',
    type=str,
    required=True
    )
parser.add_argument("--user", "-u",
    help="Default: Admin",
    default="Admin",
    type=str)
parser.add_argument("--password", "-p",
    help="Default: zabbix",
    default="zabbix",
    type=str)
args = parser.parse_args()
if not args.server.__contains__("https://" or "http://"): args.server = "https://"+args.server


#Time in seconds to offset timestamp from the beginer of the day to the end
dayInSeconds = 86400

default_arg_all_dependencies = {
    "output": "extend",
    "selectDependencies": "extend"
}

print_dict = lambda data : print(json.dumps(data,indent=4))

class timedate():
    def __init__(self,):
        self.today = date.today()

    def get_all_days_of_last_month_timestamp(self,):
        num_days = calendar.monthrange(self.today.year, self.today.month-1)[1]
        days = [date(self.today.year, self.today.month-1, day) for day in range(1, num_days+1)]
        ts = []
        for day in days:
            ts.append([
                int(datetime(day.year,day.month,day.day).timestamp()),
                int(datetime(day.year,day.month,day.day).timestamp()+dayInSeconds)
            ])
        return ts

    def getDur(self, data):
        if data == 0:
            return time(0,0,0)
        day = int(data/86400)
        if day:
            return time(23,59,59)
        hours = int(data/3600)
        if hours: data = data - hours*3600
        minutes = int(data/60)
        if minutes: data = data - minutes*60
        seconds = int(data)
        return time(hours,minutes,seconds)

class zbx():
    def __init__(self,server:str,user:str,password:str):
        self.client = ZabbixAPI(server=server,timeout=30,log_level=logging.CRITICAL)
        self.client.login(user=user,password=password)

    def get_all_sla_info(self,):
        return self.client.service.get(default_arg_all_dependencies)

    def get_sla_dependencies(self, data:dict):
        return data['dependencies']
    
    def get_sla_dependencies_id(self, data:list):
        ids = []
        [ids.append(int(dep['linkid'])) for dep in self.get_sla_dependencies(data)]
        return ids

    def get_sla(self, id, f, t):
        data = {
                "serviceids": str(id),
                "intervals": [
                    {
                        "from": f,
                        "to": t
                    }
                ]
            }
        return self.client.service.getsla(data)

    def get_sla_detailed_of_interval(self, id, month:list):
        results = []
        [results.append(self.get_sla(id, day[0],day[1])) for day in month]
        return results
    
    def parser_sla_detailed_of_interval(self,data:list):
        WholeMonth = list()
        for day in data:
            day = day[list(day.keys())[0]]
            DayDictData = {
                "date" : date.fromtimestamp(day['sla'][0]['from']),
                "slaUP" : round(day['sla'][0]['sla']/100,3),
                "slaDOWN" : 1.0-round(day['sla'][0]['sla']/100,3),
                "timeUP": timedate().getDur(day['sla'][0]['okTime']),
                "timeDOWN": timedate().getDur(day['sla'][0]['problemTime'])
            }
            # print(DayDictData)
            WholeMonth.append(DayDictData)
        return WholeMonth
            

if __name__ == "__main__":
    try:
        print(f"Server 👌 - {args.server}")
        cl = zbx(args.server,args.user,args.password)
        all_slas = cl.get_all_sla_info()
        begin = True
        while begin:
            [print(f"{i}: {sla['name']}") for sla,i in zip(all_slas,range(len(all_slas)))]
            selected = int(input("Digite o codigo de um dos SLA's: "))
            for sla,i in zip(all_slas,range(len(all_slas))):
                if selected == i:
                    cal = timedate().get_all_days_of_last_month_timestamp()
                    results = cl.get_sla_detailed_of_interval(sla['serviceid'],cal)
                    results = cl.parser_sla_detailed_of_interval(results)
                    df = pd.DataFrame(results)
                    df['date'] = pd.to_datetime(df['date'])
                    with pd.ExcelWriter('saved.xlsx',engine='openpyxl') as writer:
                        df.to_excel(writer,sheet_name=sla['name'][:31])
            begin = int(input("Outro SLA? 0-Não 1-Sim: "))

    except Exception as err:
        print(err,'\n')