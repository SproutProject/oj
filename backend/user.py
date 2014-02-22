import base64
import bcrypt
import psycopg2

import config

class UserService:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 32
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3

    ACCTID_GUEST = 0

    def __init__(self,db,mc):
        self.db = db
        self.mc = mc

        UserService.inst = self

    def signin(self,mail,pw):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "acct_id","password" FROM "account" '
            'WHERE "mail" = %s;'),
            (mail,))

        if cur.rowcount != 1:
            return ('Esign',None)

        acct_id,hpw = cur.fetchone()
        hpw = base64.b64decode(hpw.encode('utf-8'))

        if bcrypt.hashpw(pw.encode('utf-8'),hpw) == hpw:
            return (None,acct_id)

        return ('Esign',None)

    def signup(self,mail,pw,name):
        if len(mail) < UserService.MAIL_MIN:
            return ('Emailmin',None)
        if len(mail) > UserService.MAIL_MAX:
            return ('Emailmax',None)
        if len(pw) < UserService.PW_MIN:
            return ('Epwmin',None)
        if len(pw) > UserService.PW_MAX:
            return ('Epwmax',None)
        if len(name) < UserService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > UserService.NAME_MAX:
            return ('Enamemax',None)

        hpw = bcrypt.hashpw(pw.encode('utf-8'),bcrypt.gensalt(12))

        cur = yield self.db.cursor()
        try:
            yield cur.execute(('INSERT INTO "account" '
                '("mail","password","name","acct_type") '
                'VALUES (%s,%s,%s,%s) RETURNING "acct_id";'),
                (mail,base64.b64encode(hpw).decode('utf-8'),name,
                    UserService.ACCTTYPE_USER))

        except psycopg2.IntegrityError:
            return ('Eexist',None)

        if cur.rowcount != 1:
            return ('Eunk',None)

        return (None,cur.fetchone()[0])

    def getsign(self,req):
        acct_id = req.get_secure_cookie('id')
        if acct_id == None:
            return ('Esign',None)

        acct_id = int(acct_id)

        acct = yield self.mc.get('account@%d'%acct_id)
        if acct == None:
            cur = yield self.db.cursor()
            yield cur.execute('SELECT 1 FROM "account" WHERE "acct_id" = %s;',
                    (acct_id,))

            if cur.rowcount != 1:
                return ('Esign',None)

        return (None,acct_id)

    def getinfo(self,acct_id):
        acct = yield self.mc.get('account@%d'%acct_id)
        if acct == None:
            cur = yield self.db.cursor()
            yield cur.execute(('SELECT "mail","name","acct_type",'
                '"class","photo","cover" '
                'FROM "account" WHERE "acct_id" = %s;'),
                (acct_id,))
            if cur.rowcount != 1:
                return ('Enoext',None)

            mail,name,acct_type,clas,photo,cover = cur.fetchone()
            acct = {
                'acct_id':acct_id,
                'acct_type':acct_type,
                'class':clas[0],
                'mail':mail,
                'name':name,
                'photo':photo,
                'cover':cover
            }

            yield self.mc.set('account@%d'%acct_id,acct)

        return (None,{
            'acct_id':acct['acct_id'],
            'acct_type':acct['acct_type'],
            'class':acct['class'],
            'name':acct['name'],
            'photo':acct['photo'],
            'cover':acct['cover']
        })

    def update_acct(self,acct_id,acct_type,clas,name,photo,cover):
        if (acct_type not in
                [UserService.ACCTTYPE_KERNEL,UserService.ACCTTYPE_USER]):
            return ('Eparam',None)
        if clas not in [0,1,2]:
            return ('Eparam',None)
        if len(name) < UserService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > UserService.NAME_MAX:
            return ('Enamemax',None)

        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "account" '
            'SET "acct_type" = %s,"class" = \'{%s}\',"name" = %s,'
            '"photo" = %s,"cover" = %s '
            'WHERE "acct_id" = %s;'),
            (acct_type,clas,name,photo,cover,acct_id))
        if cur.rowcount != 1:
            return ('Enoext',None)

        yield self.mc.delete('account@%d'%acct_id)
        yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        return (None,None)

    def reset_pw(self,acct_id,old,pw):
        if len(pw) < UserService.PW_MIN:
            return ('Epwmin',None)
        if len(pw) > UserService.PW_MAX:
            return ('Epwmax',None)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "password" FROM "account" '
            'WHERE "acct_id" = %s;'),
            (acct_id,))
        if cur.rowcount != 1:
            return ('Eacct',None)

        hpw = base64.b64decode(cur.fetchone()[0].encode('utf-8'))
        if bcrypt.hashpw(old.encode('utf-8'),hpw) != hpw:
            return ('Epwold',None)

        hpw = bcrypt.hashpw(pw.encode('utf-8'),bcrypt.gensalt(12))
        yield cur.execute(('UPDATE "account" SET "password" = %s '
            'WHERE "acct_id" = %s;'),
            (base64.b64encode(hpw).decode('utf-8'),acct_id))

        return (None,None)

    def list_acct(self):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "acct_id","acct_type","name","mail","class" '
            'FROM "account" ORDER BY "acct_id" ASC;'))

        acctlist = []
        for acct_id,acct_type,name,mail,clas in cur:
            acctlist.append({
                'acct_id':acct_id,
                'acct_type':acct_type,
                'name':name,
                'mail':mail,
                'class':clas[0]
            })

        return (None,acctlist)
