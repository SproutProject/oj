import os
import json
import datetime

from user import UserConst
from req import RequestHandler
from req import reqenv
from req import Service

class ManageHandler(RequestHandler):
    @reqenv
    def get(self,page = 'dash'):
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.finish('Eacces')
            return

        if page == 'dash':
            self.render('manage-dash',page = page)
            return

        elif page == 'pro':
            err,prolist = yield from Service.Pro.list_pro(self.acct)

            self.render('manage-pro',page = page,prolist = prolist)
            return

        elif page == 'addpro':
            self.render('manage-pro-add',page = page)
            return

        elif page == 'updatepro':
            pro_id = int(self.get_argument('proid'))

            err,pro = yield from Service.Pro.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

            self.render('manage-pro-update',page = page,pro = pro)
            return

        elif page == 'acct':
            err,acctlist = yield from Service.Acct.list_acct(
                    UserConst.ACCTTYPE_KERNEL,True)

            self.render('manage-acct',page = page,acctlist = acctlist)
            return

        elif page == 'updateacct':
            acct_id = int(self.get_argument('acctid'))

            err,acct = yield from Service.Acct.info_acct(acct_id)

            self.render('manage-acct-update',page = page,acct = acct)
            return

    @reqenv
    def post(self,page):
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.finish('Eacces')
            return

        if page == 'pack':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'gettoken':
                err,pack_token = Service.Pack.gen_token()
                self.finish(json.dumps(pack_token))
                return

        elif page == 'pro':
            reqtype = self.get_argument('reqtype')
            
            if reqtype == 'addpro':
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = self.get_argument('expire')
                pack_token = self.get_argument('pack_token')
                
                if expire == '':
                    expire = None

                else:
                    try:
                        expire = datetime.datetime.strptime(expire,
                                '%Y-%m-%dT%H:%M:%S.%fZ')
                        expire = expire.replace(tzinfo = datetime.timezone.utc)

                    except ValueError:
                        self.finish('Eexpire')
                        return

                err,pro_id = yield from Service.Pro.add_pro(
                        name,status,clas,expire,pack_token)
                if err:
                    self.finish(err)
                    return

                self.finish(json.dumps(pro_id))
                return

            elif reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = self.get_argument('expire')
                pack_type = int(self.get_argument('pack_type'))
                pack_token = self.get_argument('pack_token')

                if expire == '':
                    expire = None

                else:
                    try:
                        expire = datetime.datetime.strptime(expire,
                                '%Y-%m-%dT%H:%M:%S.%fZ')
                        expire = expire.replace(tzinfo = datetime.timezone.utc)

                    except ValueError:
                        self.finish('Eexpire')
                        return

                if pack_token == '':
                    pack_token = None

                err,ret = yield from Service.Pro.update_pro(
                        pro_id,name,status,clas,expire,pack_type,pack_token)
                if err:
                    self.finish(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'rechal':
                pro_id = int(self.get_argument('pro_id'))

                err,pro = yield from Service.Pro.get_pro(pro_id,self.acct)
                if err:
                    self.finish(err)
                    return

                cur = yield self.db.cursor()
                yield cur.execute(('SELECT "chal_id" FROM "challenge" '
                    'WHERE "pro_id" = %s'),
                    (pro_id,))

                for chal_id, in cur:
                    err,ret = yield from Service.Chal.reset_chal(chal_id)
                    err,ret = yield from Service.Chal.emit_chal(
                            chal_id,
                            pro_id,
                            pro['testm_conf'],
                            os.path.abspath('code/%d/main.cpp'%chal_id),
                            os.path.abspath('problem/%d/res'%pro_id))

                self.finish('S')
                return

        elif page == 'acct':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'updateacct':
                acct_id = int(self.get_argument('acct_id'))
                acct_type = int(self.get_argument('acct_type'))
                clas = int(self.get_argument('class'))

                err,acct = yield from Service.Acct.info_acct(acct_id)
                if err:
                    self.finish(err)
                    return

                err,ret = yield from Service.Acct.update_acct(acct_id,
                        acct_type,clas,acct['name'],acct['photo'],acct['cover'])
                if err:
                    self.finish(err)
                    return

                self.finish('S')
                return

        self.finish('Eunk')
        return
