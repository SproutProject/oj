import os
import json
import tornado.process
import tornado.concurrent

from req import RequestHandler
from req import reqenv
from user import UserService
from chal import ChalService
from pack import PackService

class ProService:
    NAME_MIN = 1
    NAME_MAX = 64
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

    def __init__(self,db,mc):
        self.db = db
        self.mc = mc

        ProService.inst = self

    def get_pro(self,pro_id,acct):
        max_status = self._get_acct_limit(acct)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "pro_id","name","status" FROM "problem" '
            'WHERE "pro_id" = %s AND "status" <= %s;'),
            (pro_id,max_status))

        if cur.rowcount != 1:
            return ('Enoext',None)

        pro_id,name,status = cur.fetchone()

        if status < ProService.STATUS_OFFLINE:
            pro_f = open('problem/%d/conf.json'%pro_id)
            conf = json.load(pro_f)
            pro_f.close()

        else:
            conf = None

        return (None,{
            'pro_id':pro_id,
            'name':name,
            'status':status,
            'conf':conf
        })

    def list_pro(self,max_status = STATUS_ONLINE):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "pro_id","name","status" FROM "problem" '
            'WHERE "status" <= %s ORDER BY "pro_id" ASC;'),
            (max_status,))

        prolist = list()
        for pro_id,name,status in cur:
            prolist.append({
                'pro_id':pro_id,
                'name':name,
                'status':status
            })

        return (None,prolist)

    def add_pro(self,name,status,pack_token = None):
        size = len(name)
        if size < ProService.NAME_MIN:
            return ('Enamemin',None)
        if size > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)

        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "problem" '
            '("name","status") '
            'VALUES (%s,%s) RETURNING "pro_id";'),
            (name,status))

        if cur.rowcount != 1:
            return ('Eunk',None)
        
        pro_id = cur.fetchone()[0]

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)

        return (None,pro_id)

    def update_pro(self,pro_id,name,status,pack_token = None):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)

        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "problem" '
            'SET "name" = %s,"status" = %s '
            'WHERE "pro_id" = %s;'),
            (name,status,pro_id))

        if cur.rowcount != 1:
            return ('Eunk',None)

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)
        
        return (None,None)

    def _get_acct_limit(self,acct):
        if acct['type'] == UserService.ACCTTYPE_KERNEL:
            return ProService.STATUS_OFFLINE

        else:
            return ProService.STATUS_ONLINE

    def _unpack_pro(self,pro_id,pack_token):
        err,ret = yield from PackService.inst.unpack(
                pack_token,'problem/%d'%pro_id,True)
        if err:
            return (err,None)

        os.chmod('problem/%d'%pro_id,0o755)
        try:
            os.symlink(os.path.abspath('problem/%d/http'%pro_id),
                    '../http/problem/%d'%pro_id)

        except FileExistsError:
            pass

        return (None,None)

class ProsetHandler(RequestHandler):
    @reqenv
    def get(self):
        err,prolist = yield from ProService.inst.list_pro()
        self.render('proset',prolist = prolist)
        return

    @reqenv
    def psot(self):
        pass

class ProHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        pro_id = int(pro_id)

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        self.render('pro',pro = pro)
        return

class SubmitHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Esign')
            return

        pro_id = int(pro_id)

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        self.render('submit',pro = pro)
        return

    @reqenv
    def post(self):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Esign')
            return

        reqtype = self.get_argument('reqtype')
        if reqtype == 'submit':
            pro_id = int(self.get_argument('pro_id'))
            code = self.get_argument('code')

            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

            err,chal_id = yield from ChalService.inst.add_chal(
                    pro_id,self.acct['acct_id'],code)
            if err:
                self.finish(err)
                return

        elif reqtype == 'rechal':
            chal_id = int(self.get_argument('chal_id'))

            err,ret = yield from ChalService.inst.reset_chal(chal_id)
            err,chal = yield from ChalService.inst.get_chal(chal_id)
            pro_id = chal['pro_id']

            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

        else:
            self.finish('Eparam')
            return

        err,ret = yield from ChalService.inst.emit_chal(
                chal_id,
                pro['conf']['timelimit'],
                pro['conf']['memlimit'],
                pro['conf']['test'],
                os.path.abspath('code/%d/main.cpp'%chal_id),
                os.path.abspath('problem/%d/testdata'%pro_id))
        if err:
            self.finish(err)
            return

        self.finish(json.dumps(chal_id))
        return

class ChalHandler(RequestHandler):
    @reqenv
    def get(self,chal_id):
        chal_id = int(chal_id)

        err,chal = yield from ChalService.inst.get_chal(chal_id)
        if err:
            self.finish(err)
            return

        err,pro = yield from ProService.inst.get_pro(chal['pro_id'],self.acct)
        if err:
            self.finish(err)
            return

        if (chal['acct_id'] != self.acct['acct_id'] and
                self.acct['type'] != UserService.ACCTTYPE_KERNEL):
            chal['code'] = None

        self.render('chal',pro = pro,chal = chal)
        return

    @reqenv
    def post(self):
        reqtype = self.get_argument('reqtype')
        self.finish('Eunk')
        return
