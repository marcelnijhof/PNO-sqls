
import pyodbc

from datetime import datetime
import os
import sys
from loguru import logger
from configparser import ConfigParser



### read config.ini file
config_object = ConfigParser()
config_object.read('config.ini')

logger.remove()  # Remove the default handler.
logger.add(sys.stderr, format="{time} - {level} - {message}")  # Log to console with custom format.
logger.add("logs/pnosqls.log", level="INFO", rotation="500 MB")  # Also log to a file, rotating every 500 MB.



## folders
downloadpath = config_object['VARIABLES']['downloadpath']
#downloadpath = 'C:\\Users\\Marcel.Nijhof\\OneDrive - PNO Consultants\\WBSO\\BB\\2026\\Mededelingen\\'#$2023\\Aanvragen\\'
uploadpath = config_object['VARIABLES']['uploadpath']
#uploadpath = 'C:\\Users\\Marcel.Nijhof\\OneDrive - PNO Consultants\\WBSO\\BB\\2026\\Aanvragen\\'
#mededelingpath = 'C:\\Users\\Marcel.Nijhof\\OneDrive - PNO Consultants\\WBSO\\BB\\2026\\Mededelingen\\'

#database
driver = config_object['DATABASE_CONNECTION']['driver']	
server = config_object['DATABASE_CONNECTION']['server']
database = config_object['DATABASE_CONNECTION']['database']
uid = os.environ.get("DB_USER_ID")
pwd = os.environ.get("DB_PASSWORD")
cnxn_string = "Driver={};SERVER={};DATABASE={};UID={};PWD={};".format(driver,server,database,uid,pwd)
cnxnlcl_string = "Driver={};SERVER={};DATABASE={};UID={};PWD={};".format(driver,server,database,uid,pwd)

print('Connecting to database...')
try:
    cnxn=pyodbc.connect(cnxn_string)
    logger.info('Database connection established')
except Exception as e:
	logger.error(f'Database connection failed: {e}')
	print('Database connection failed: ', e)
	try:		
		cnxn=pyodbc.connect(cnxn_string)
		logger.info('Database connection established on second attempt')	
	except Exception as e:
		logger.error(f'Second attempt at database connection failed: {e}')
		print('Second attempt at database connection failed: ', e)
		sys.exit(1)


#check for proforma deadlines and update masterplanning if necessary
def check_proforma_deadlines():
    logger.info('first step: check for Proforma deadlines and update masterplanning if necessary')
    mycursor = cnxn.cursor()
    aanvulling_proforma_query_test = "with proforma as (select distinct a.id, cast(re.termijn as date) as termijn\
        from p_wbso.dbo.aanvraag as a\
            inner join p_wbso.afas.projtable as pt\
                on a.projid = pt.proj_id\
            left join p_wbso.pno.rvo_email as re\
                on pt.pyl_proj_request_number = re.referentie\
            where a.periodeid>=60\
            and re.type like 'aanvullen%')\
            select mplan.application_id,pf.termijn\
            from p_wbso.dbo.masterplanning as mplan\
            inner join proforma as pf\
                on mplan.application_id = pf.id\
            where mplan.deadlineaanvullingproforma is null"
    aanvulling_proforma_query = "with proforma as (select distinct a.id, cast(re.termijn as date) as termijn\
        from p_wbso.dbo.aanvraag as a\
            inner join p_wbso.afas.projtable as pt\
                on a.projid = pt.proj_id\
            left join p_wbso.pno.rvo_email as re\
                on pt.pyl_proj_request_number = re.referentie\
            where a.periodeid>=60\
            and re.type like 'aanvullen%')\
            update p_wbso.dbo.masterplanning\
            set deadlineaanvullingproforma = pf.termijn\
            from p_wbso.dbo.masterplanning as mplan\
            inner join proforma as pf\
                on mplan.application_id = pf.id\
            where mplan.deadlineaanvullingproforma is null"
    #aanvullingsdatum hiermee gezet in masterplanning, zodat deze kan worden meegenomen in de planning van de aanvragen


    mycursor.execute(aanvulling_proforma_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(aanvulling_proforma_query)
        mycursor.commit()
        logger.info(f'Deadline proforma query executed successfully, {len(results)} updated in masterplanning')
    else:
        logger.info('No results found for the deadline proforma query')


def check_eerste_vragenbrieven(): 
#check for eerste vragenbrieven en update masterplanning if necessary

    logger.info('second step: check for eerste vragenbrieven en update masterplanning if necessary')
    eerste_vragenbrieven_query_test = "with kanbriefnw as( \
                                        select distinct a.id, re.termijn \
                                        from p_wbso.dbo.aanvraag as a \
                                        inner join p_wbso.afas.projtable as pt \
                                            on a.projid = pt.proj_id \
                                        left join p_wbso.pno.rvo_email as re \
                                            on pt.pyl_proj_request_number = re.referentie \
                                        where a.periodeid>=60 \
                                        and a.aanvraagstatus='INGEDIEND_RVO' \
                                        and re.type='Vragen wbso' \
                                    ) \
                                    select mp.application_id, kb.termijn, kb.id \
                                    from p_wbso.dbo.masterplanning as mp \
                                    inner join kanbriefnw as kb \
                                        on mp.application_id = kb.id \
                                    where mp.vragenbrief = 0 \
                                    or mp.deadline_kan_brief is null"
    eerste_vragenbrieven_query = "with kanbriefnw as( \
                                        select distinct a.id, re.termijn \
                                        from p_wbso.dbo.aanvraag as a \
                                        inner join p_wbso.afas.projtable as pt \
                                            on a.projid = pt.proj_id \
                                        left join p_wbso.pno.rvo_email as re \
                                            on pt.pyl_proj_request_number = re.referentie \
                                        where a.periodeid>=60 \
                                        and a.aanvraagstatus='INGEDIEND_RVO' \
                                        and re.type='Vragen wbso' \
                                    ) \
                                    update p_wbso.dbo.masterplanning \
                                    set vragenbrief = 1, deadline_kan_brief = kb.termijn, per_mail_vragen_gesteld = 1 \
                                    from p_wbso.dbo.masterplanning as mp \
                                    inner join kanbriefnw as kb \
                                        on mp.application_id = kb.id \
                                    where mp.vragenbrief = 0 \
                                    or mp.deadline_kan_brief is null"
    
    mycursor = cnxn.cursor()
    mycursor.execute(eerste_vragenbrieven_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(eerste_vragenbrieven_query)
        mycursor.commit()
        logger.info(f'Vragenbrieven query executed successfully, {len(results)} updated in masterplanning')
    else:  
        logger.info('No results found for the eerste vragenbrieven query')
        
#check for updates innovatiebox
def check_innovatiebox_updates():
    logger.info('third step: check for updates innovatiebox')
    innovatiebox_query_test = "select * from p_wbso.ibox.innovation_box as ib where ib.applied = 0 and ib.settlement= 1"
    innovatiebox_query = "update p_wbso.ibox.innovation_box set settlement =0 from p_wbso.ibox.innovation_box as ib where ib.applied = 0 and ib.settlement= 1"
    
    mycursor = cnxn.cursor()
    mycursor.execute(innovatiebox_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(innovatiebox_query)
        mycursor.commit()
        logger.info(f'Innovatiebox query executed successfully, {len(results)} updated in table innovation_box')
    else:
        logger.info('No results found for the innovatiebox query')

# herstel foutieve kostenplaats
def herstelfoutieve_kostenplaats():
    logger.info('fourth step: herstel foutieve kostenplaats')
    herstel_foutieve_kostenplaats_query_test = "SELECT a.pnokostenplaats,pt.dimension2_ FROM   p_wbso.dbo.aanvraag AS a INNER JOIN p_wbso.afas.projtable AS pt ON a.projid = pt.proj_id WHERE  ( a.pnokostenplaats != pt.dimension2_ ) AND a.start_datum_periode >= '2018-01-01' "
    herstel_foutieve_kostenplaats_query = "UPDATE p_wbso.dbo.aanvraag SET pnokostenplaats = pt.dimension2_ FROM   p_wbso.dbo.aanvraag AS a INNER JOIN p_wbso.afas.projtable AS pt ON a.projid = pt.proj_id WHERE  ( a.pnokostenplaats != pt.dimension2_ ) AND a.start_datum_periode >= '2018-01-01' "
    
    mycursor = cnxn.cursor()
    mycursor.execute(herstel_foutieve_kostenplaats_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor_true = cnxn.cursor()
        mycursor_true.execute(herstel_foutieve_kostenplaats_query)
        mycursor_true.commit()
        #results = mycursor_true.fetchall()
        logger.info(f'Herstel foutieve kostenplaats query executed successfully, {len(results)}, updated in table aanvraag')
    else:
        logger.info('No results found for the herstel foutieve kostenplaats query')
        
def bsn_updaten():
    logger.info('fifth step: update BSN numbers')
    bsn_update_query_test = "WITH bsnjaar2 (orgnummer, jaar, datum ,gemeldvia) AS ( \
                        select o.afas,ar.year,ar.submittedBSNAt,case when ar.submittedBSNBy ='' or ar.submittedBSNBy=NULL then 'Klant' else ar.submittedBSNBy end \
                        from P_RealisatieCheck.dbo.organisation as o\
                        inner join p_realisatiecheck.dbo.annualrealisation as ar\
                            on o.id=ar.organisationDataId\
                            and ar.submittedBSNMethod in (1,2,3))\
                        select a.id,a.periodeid,mp.bsndoorgegeven, bj2.orgnummer,bj2.jaar,bj2.datum,bj2.gemeldvia \
                        FROM   p_wbso.dbo.masterplanning AS mp \
                        INNER JOIN p_wbso.dbo.aanvraag AS a \
                            ON a.id = mp.application_id \
                        INNER JOIN bsnjaar2 AS bj2 \
                            ON a.account_num = Cast(bj2.orgnummer AS NVARCHAR) COLLATE database_default \
                        INNER JOIN p_wbso.dbo.periode AS pe \
                            ON a.periodeid = pe.id \
                        WHERE  pe.jaar = bj2.jaar + 2 \
                            AND mp.bsndoorgegeven = 0 "
    bsn_update_query =  "WITH bsnjaar2 (orgnummer, jaar, datum ,gemeldvia) AS ( \
                        select o.afas,ar.year,ar.submittedBSNAt,case when ar.submittedBSNBy ='' or ar.submittedBSNBy=NULL then 'Klant' else ar.submittedBSNBy end \
                        from P_RealisatieCheck.dbo.organisation as o\
                        inner join p_realisatiecheck.dbo.annualrealisation as ar\
                            on o.id=ar.organisationDataId\
                            and ar.submittedBSNMethod in (1,2,3))\
                        UPDATE dbo.masterplanning \
                        SET bsndoorgegeven = 1 ,bsningediend_door = bj2.gemeldvia, bsndatum_ingediend= bj2.datum \
                        FROM   p_wbso.dbo.masterplanning AS mp \
                        INNER JOIN p_wbso.dbo.aanvraag AS a \
                            ON a.id = mp.application_id \
                        INNER JOIN bsnjaar2 AS bj2 \
                            ON a.account_num = Cast(bj2.orgnummer AS NVARCHAR) COLLATE database_default \
                        INNER JOIN p_wbso.dbo.periode AS pe \
                            ON a.periodeid = pe.id \
                        WHERE  pe.jaar = bj2.jaar + 2 \
                            AND mp.bsndoorgegeven = 0 "
    mycursor = cnxn.cursor()
    mycursor.execute(bsn_update_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor_true = cnxn.cursor()
        mycursor_true.execute(bsn_update_query)
        mycursor_true.commit()
        logger.info(f'BSN update query executed successfully, {len(results)} updated in table aanvraag')
    else:
        logger.info('No results found for the BSN update query')
        
#check of er uitstelbrieven zijn en update masterplanning indien nodig
def check_uitstelbrieven():
    logger.info('sixth step: check for uitstelbrieven en update masterplanning if necessary')
    uitstelbrieven_query_test = "with zalbriefnw as( \
                                    select distinct a.id, re.termijn \
                                    from p_wbso.dbo.aanvraag as a \
                                    inner join p_wbso.afas.projtable as pt \
                                        on a.projid = pt.proj_id \
                                    left join p_wbso.pno.rvo_email as re \
                                        on pt.pyl_proj_request_number = re.referentie \
                                    where a.periodeid>=64 \
                                    and a.aanvraagstatus='INGEDIEND_RVO' \
                                    and re.type='Uitstel vragen wbso' \
                                ) \
                                select mp.application_id, kb.termijn, kb.id \
                                from p_wbso.dbo.masterplanning as mp \
                                inner join zalbriefnw as kb \
                                    on mp.application_id = kb.id \
                                where mp.vragenbrief = 0 \
                                or mp.deadline_zal_brief is null"
    uitstelbrieven_query = "with zalbriefnw as( \
                                    select distinct a.id, re.termijn \
                                    from p_wbso.dbo.aanvraag as a \
                                    inner join p_wbso.afas.projtable as pt \
                                        on a.projid = pt.proj_id \
                                    left join p_wbso.pno.rvo_email as re \
                                        on pt.pyl_proj_request_number = re.referentie \
                                    where a.periodeid>=64 \
                                    and a.aanvraagstatus='INGEDIEND_RVO' \
                                    and re.type='Uitstel vragen wbso' \
                                ) \
                                update p_wbso.dbo.masterplanning \
                                set vragenbrief = 1, deadline_zal_brief = kb.termijn, per_mail_vragen_gesteld = 1 \
                                from p_wbso.dbo.masterplanning as mp \
                                inner join zalbriefnw as kb \
                                    on mp.application_id = kb.id \
                                where mp.vragenbrief = 0 \
                                or mp.deadline_zal_brief is null"
    mycursor = cnxn.cursor()
    mycursor.execute(uitstelbrieven_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(uitstelbrieven_query)
        mycursor.commit()
        logger.info(f'Uitstelbrieven query executed successfully, {len(results)} updated in masterplanning')
    else:
        logger.info('No results found for the uitstelbrieven query')

#update ketenmachtigingen als deze verloopt
def update_ketenmachtigingen():
    logger.info('seventh step: update ketenmachtigingen als deze verloopt')
    ketenmachtigingen_query_test = "select a.id,left(ct.kvk_number,8) as kvk\
                                    from p_wbso.dbo.aanvraag as a \
                                    inner join p_wbso.afas.custable as ct \
                                        on a.account_num=ct.account_num \
                                    inner join p_wbso.afas.projtable as pt \
                                        on a.projid=pt.proj_id \
                                    inner join p_wbso.afas.administratie as adm \
                                        on pt.afas_administration=adm.administratie_id \
                                    inner join p_wbso.dbo.masterplanning as mp \
                                        on a.id=mp.application_id \
                                    inner join P_eHerkenning.dbo.Ketenmachtiging as km\
                                        on left(ct.kvk_number,8) collate database_default = left(km.KvK_nr_verlener,8) collate database_default \
                                    inner join P_eHerkenning.dbo.PNO_Entiteit as ent \
                                        on km.pno_entiteit_id=ent.ID \
                                    inner join P_eHerkenning.dbo.KetenmachtigingNiveau as kmn\
                                        on km.id=kmn.FK_Ketenmachtiging_id\
                                        and lower(kmn.dienst) in ( 'alle diensten eh3','rvo diensten op niveau eh3','alle diensten')\
                                    where a.periodeid>=66\
                                    and (kmn.Geldig_tot< a.start_datum_periode or (kmn.Geldig_tot<= getdate() and kmn.Geldig_tot<a.virtueel_eind_datum_periode ) ) \
                                    and mp.ketenmachtiging_verleend=1\
                                    and adm.naam=ltrim(rtrim(ent.PNO_Entiteit_Naam)) collate database_default"
    ketenmachtigingen_query = "update masterplanning\
                                    set ketenmachtiging_verleend=0\
                                    from p_wbso.dbo.aanvraag as a \
                                    inner join p_wbso.afas.custable as ct \
                                        on a.account_num=ct.account_num \
                                    inner join p_wbso.afas.projtable as pt \
                                        on a.projid=pt.proj_id \
                                    inner join p_wbso.afas.administratie as adm \
                                        on pt.afas_administration=adm.administratie_id \
                                    inner join p_wbso.dbo.masterplanning as mp \
                                        on a.id=mp.application_id \
                                    inner join P_eHerkenning.dbo.Ketenmachtiging as km\
                                        on left(ct.kvk_number,8) collate database_default = left(km.KvK_nr_verlener,8) collate database_default \
                                    inner join P_eHerkenning.dbo.PNO_Entiteit as ent \
                                        on km.pno_entiteit_id=ent.ID \
                                    inner join P_eHerkenning.dbo.KetenmachtigingNiveau as kmn\
                                        on km.id=kmn.FK_Ketenmachtiging_id\
                                        and lower(kmn.dienst) in ( 'alle diensten eh3','rvo diensten op niveau eh3','alle diensten')\
                                    where a.periodeid>=66\
                                    and (kmn.Geldig_tot< a.start_datum_periode or (kmn.Geldig_tot<= getdate() and kmn.Geldig_tot<a.virtueel_eind_datum_periode ) ) \
                                    and mp.ketenmachtiging_verleend=1\
                                    and adm.naam=ltrim(rtrim(ent.PNO_Entiteit_Naam)) collate database_default"
    
    mycursor = cnxn.cursor()
    mycursor.execute(ketenmachtigingen_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(ketenmachtigingen_query)
        mycursor.commit()
        logger.info(f'Ketenmachtigingen update query executed successfully, {len(results)} updated in table masterplanning')
    else:
        logger.info('No results found for the ketenmachtigingen update query')
        
# beschikking check RVO-email en berichtenbox
def check_beschikking_rvo_email_berichtenbox():
    logger.info('eighth step: check for beschikkingen in RVO-email and berichtenbox')
    beschikking_query_test = "select distinct a.id,a.account_num,ct.pyl_juridic_name,pt.afas_administration as intermediair,pt.pyl_proj_request_number as referentie_ERP,trim(re.referentie) as referentie_by_mail,re.received as receved_by_mail,b.Referentienummer,b.Briefdatum\
                                from p_wbso.dbo.aanvraag as a\
                                inner join p_wbso.afas.custable as ct\
                                on a.account_num=ct.account_num\
                                inner join p_wbso.afas.projtable as pt\
                                on a.projid=pt.proj_id\
                                left join p_wbso.pno.rvo_email as re\
                                on pt.pyl_proj_request_number=re.referentie\
                                and re.Type like 'Beschikking%'\
                                left join p_wbso.pno.Beschikking as b\
                                on a.id=b.Aanvraagid\
                                where a.periodeid=68\
                                and a.aanvraagstatus='INGEDIEND_RVO'\
                                and re.referentie is not null\
                                and b.Referentienummer is null"

    mycursor = cnxn.cursor()
    mycursor.execute(beschikking_query_test)
    results = mycursor.fetchall()
    if results:
        logger.info(f'Beschikking query executed successfully, {len(results)}, only Zelfstandigen should be shown in the results, check if this is correct')
        for result in results:
            logger.info(f'App I= {result.id} Org ID={result.account_num} Org name= {result.pyl_juridic_name} Adm ID= {result.intermediair} Ref ERP= {result.referentie_ERP} Ref in mail= {result.referentie_by_mail} Received mail= {result.receved_by_mail} ')   
            
    else:
        logger.info('No results found for the beschikking query')

# check verschil afas-beschikking en wbso-beschikking
def check_afas_wbso_beschikking():
    logger.info('ninth step: check for differences between afas-beschikking and wbso-beschikking')
    afas_wbso_beschikking_query_test = "select distinct bes.Aanvraagid,bes.Afasprojnr,bes.Max_afdrachtvermindering,bes.Briefdatum,ppopt.category_id,ppopt.proj_id,ppopt.pyl_price,ppopt.trans_date,bes.Max_afdrachtvermindering-ppopt.pyl_price as verschil\
                                    from pno.beschikking as bes\
                                    left join afas.pylprojohwpitrans as ppopt\
                                    on bes.Afasprojnr=ppopt.proj_id\
                                    and ppopt.category_id='Toezegging'\
                                    left join dbo.aanvraag as a\
                                    on bes.Aanvraagid=a.id\
                                    where (bes.Max_afdrachtvermindering-ppopt.pyl_price >1 or bes.Max_afdrachtvermindering-ppopt.pyl_price <-1)\
                                    and bes.briefdatum> '2025-12-31'\
                                    and a.aanvraagstatus in ('INGEDIEND_RVO','KLANT_STUURT_IN')\
                                    order by 8,4"

    mycursor = cnxn.cursor()
    mycursor.execute(afas_wbso_beschikking_query_test)
    results = mycursor.fetchall()
    if results:
        logger.info(f'Afas-WBSO Beschikking query executed successfully, {len(results)} differences found')
        for result in results:
            logger.info(f'App ID= {result.Aanvraagid} Projectnr= {result.Afasprojnr} Aanvraagwaarde= {result.Max_afdrachtvermindering} Briefdatum= {result.Briefdatum} Category= {result.category_id} Proj ID= {result.proj_id} Pyl Price= {result.pyl_price} PylDatum={result.trans_date} Verschil= {result.verschil}')   

    else:
        logger.info('No differences found between afas-beschikking and wbso-beschikking')
        
# goedgekeurde uren updaten in project
def update_goedgekeurde_uren_in_project():
    logger.info('tenth step: update goedgekeurde uren in project')
    update_goedgekeurde_uren_query_test = "select bes.Aanvraagid,p.id,bp.WBSOProjectID, p.uren_goed_gekeurd,bp.SO_uren_toegekend,p.kosten_goed_gekeurd,bp.Kosten_toegekend,p.uitgaven_goed_gekeurd,bp.Uitgaven_toegekend\
                                        from pno.Beschikking_projecten as bp\
                                        inner join pno.Beschikking as bes\
                                        on bp.FK_beschikking_id=bes.ID\
                                        left join dbo.project as p\
                                        on bp.WBSOProjectID=p.id\
                                        and p.actief=1\
                                        where bp.SO_uren_toegekend-p.uren_goed_gekeurd !=0 "
    update_goedgekeurde_uren_query = "update project\
                                        set uren_goed_gekeurd=bp.SO_uren_toegekend,project_goed_gekeurd=0\
                                        from pno.Beschikking_projecten as bp\
                                        inner join pno.Beschikking as bes\
                                        on bp.FK_beschikking_id=bes.ID\
                                        left join dbo.project as p\
                                        on bp.WBSOProjectID=p.id\
                                        and p.actief=1\
                                        where bp.SO_uren_toegekend-p.uren_goed_gekeurd !=0 "
    mycursor = cnxn.cursor()
    mycursor.execute(update_goedgekeurde_uren_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(update_goedgekeurde_uren_query)
        mycursor.commit()
        logger.info(f'Update goedgekeurde uren query executed successfully, {len(results)} updated in table projtable')
    else:
        logger.info('No results found for the update goedgekeurde uren query')
        
# goedgekeurde kosten updaten in project
def update_goedgekeurde_kosten_in_project():
    logger.info('eleventh step: update goedgekeurde kosten in project')
    update_goedgekeurde_kosten_query_test = "select bes.Aanvraagid,p.id,bp.WBSOProjectID, p.kosten_goed_gekeurd,bp.Kosten_toegekend\
                                        from pno.Beschikking_projecten as bp\
                                        inner join pno.Beschikking as bes\
                                        on bp.FK_beschikking_id=bes.ID\
                                        left join dbo.project as p\
                                        on bp.WBSOProjectID=p.id\
                                        and p.actief=1\
                                        where bp.Kosten_toegekend-p.kosten_goed_gekeurd !=0  "
    update_goedgekeurde_kosten_query = "update project\
                                        set kosten_goed_gekeurd=bp.Kosten_toegekend,project_goed_gekeurd=0\
                                        from pno.Beschikking_projecten as bp\
                                        inner join pno.Beschikking as bes\
                                        on bp.FK_beschikking_id=bes.ID\
                                        left join dbo.project as p\
                                        on bp.WBSOProjectID=p.id\
                                        and p.actief=1\
                                        where bp.Kosten_toegekend-p.kosten_goed_gekeurd !=0  "
    mycursor = cnxn.cursor()
    mycursor.execute(update_goedgekeurde_kosten_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(update_goedgekeurde_kosten_query)
        mycursor.commit()
        logger.info(f'Update goedgekeurde kosten query executed successfully, {len(results)} updated in table projtable')
    else:
        logger.info('No results found for the update goedgekeurde kosten query')
        
#goedgekeurde uitgaven updaten in project
def update_goedgekeurde_uitgaven_in_project():
    logger.info('twelfth step: update goedgekeurde uitgaven in project')
    update_goedgekeurde_uitgaven_query_test = "select bes.Aanvraagid,p.id,bp.WBSOProjectID, p.uitgaven_goed_gekeurd,bp.Uitgaven_toegekend\
                                        from pno.Beschikking_projecten as bp\
                                        inner join pno.Beschikking as bes\
                                        on bp.FK_beschikking_id=bes.ID\
                                        left join dbo.project as p\
                                        on bp.WBSOProjectID=p.id\
                                        and p.actief=1\
                                        where bp.Uitgaven_toegekend-p.uitgaven_goed_gekeurd !=0  "
    update_goedgekeurde_uitgaven_query = "update project\
                                        set uitgaven_goed_gekeurd=bp.Uitgaven_toegekend,project_goed_gekeurd=0\
                                        from pno.Beschikking_projecten as bp\
                                        inner join pno.Beschikking as bes\
                                        on bp.FK_beschikking_id=bes.ID\
                                        left join dbo.project as p\
                                        on bp.WBSOProjectID=p.id\
                                        and p.actief=1\
                                        where bp.Uitgaven_toegekend-p.uitgaven_goed_gekeurd !=0  "
    mycursor = cnxn.cursor()
    mycursor.execute(update_goedgekeurde_uitgaven_query_test)
    results = mycursor.fetchall()
    if results:
        mycursor.execute(update_goedgekeurde_uitgaven_query)
        mycursor.commit()
        logger.info(f'Update goedgekeurde uitgaven query executed successfully, {len(results)} updated in table projtable')
    else:
        logger.info('No results found for the update goedgekeurde uitgaven query')
        
# Uurloon verschillen tussen afas en wbso-beschikking
def check_uurloon_afas_wbso_beschikking():
    logger.info('thirteenth step: check for differences in uurloon between afas and wbso-beschikking')
    uurloon_afas_wbso_query_test = "select b.aanvraagid,afasprojnr,a.souurloon,b.SO_uurloon as uurloon_beschikking\
                                    from p_wbso.dbo.aanvraag as a\
                                    left join p_wbso.pno.beschikking as b\
                                    on a.id=b.Aanvraagid\
                                    where b.Referentienummer like 'SO26%'\
                                    and a.souurloon != b.SO_uurloon\
                                    and b.SO_uurloon !=0"
    mycursor = cnxn.cursor()
    mycursor.execute(uurloon_afas_wbso_query_test)  
    results = mycursor.fetchall()   
    if results:
        logger.info(f'Uurloon Afas-WBSO Beschikking query executed successfully, {len(results)} differences found')
        for result in results:
            logger.info(f'Aanvraag ID= {result.aanvraagid} Afas Proj Nr= {result.afasprojnr} Souurloon= {result.souurloon} Uurloon Beschikking= {result.uurloon_beschikking}')   

    else:
        logger.info('No differences found in uurloon between afas and wbso-beschikking')

        
#main
try:
    logger.info('Script started')
    check_proforma_deadlines()
    check_eerste_vragenbrieven()
    check_innovatiebox_updates()
    herstelfoutieve_kostenplaats()
    bsn_updaten()
    check_uitstelbrieven()
    update_ketenmachtigingen()
    check_beschikking_rvo_email_berichtenbox()
    check_afas_wbso_beschikking()
    update_goedgekeurde_uren_in_project()
    update_goedgekeurde_kosten_in_project()
    update_goedgekeurde_uitgaven_in_project()
    check_uurloon_afas_wbso_beschikking()
except Exception as e:
    logger.error(f'An error occurred: {e}')
    print('An error occurred: ', e)

einde = input('Druk op Enter om af te sluiten...')
