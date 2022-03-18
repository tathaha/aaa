from server.config import Constant
from server.sql import Connect
import time
import json
import server.arcworld
import hashlib
from setting import Config


def b2int(x):
    # int与布尔值转换
    if x:
        return 1
    else:
        return 0


def int2b(x):
    # int与布尔值转换
    if x is None or x == 0:
        return False
    else:
        return True


def md5(code):
    # md5加密算法
    code = code.encode()
    md5s = hashlib.md5()
    md5s.update(code)
    codes = md5s.hexdigest()

    return codes


def get_score(c, user_id, song_id, difficulty):
    # 根据user_id、song_id、难度得到该曲目最好成绩，返回字典
    c.execute('''select * from best_score where user_id = :a and song_id = :b and difficulty = :c''',
              {'a': user_id, 'b': song_id, 'c': difficulty})
    x = c.fetchone()
    if x is not None:
        c.execute('''select name, character_id, is_skill_sealed, is_char_uncapped, is_char_uncapped_override, favorite_character from user where user_id = :a''', {
                  'a': user_id})
        y = c.fetchone()
        if y is not None:
            character = y[1]
            is_char_uncapped = int2b(y[3])
            if y[5] != -1:
                character = y[5]
                if not Config.CHARACTER_FULL_UNLOCK:
                    c.execute('''select is_uncapped, is_uncapped_override from user_char where user_id=:a and character_id=:b''', {
                        'a': user_id, 'b': character})
                else:
                    c.execute('''select is_uncapped, is_uncapped_override from user_char_full where user_id=:a and character_id=:b''', {
                        'a': user_id, 'b': character})
                z = c.fetchone()
                if z:
                    if z[1] == 0:
                        is_char_uncapped = int2b(z[0])
                    else:
                        is_char_uncapped = False
            else:
                if y[4] == 1:
                    is_char_uncapped = False

            return {
                "user_id": x[0],
                "song_id": x[1],
                "difficulty": x[2],
                "score": x[3],
                "shiny_perfect_count": x[4],
                "perfect_count": x[5],
                "near_count": x[6],
                "miss_count": x[7],
                "health": x[8],
                "modifier": x[9],
                "time_played": x[10],
                "best_clear_type": x[11],
                "clear_type": x[12],
                "name": y[0],
                "character": character,
                "is_skill_sealed": int2b(y[2]),
                "is_char_uncapped": is_char_uncapped
            }
        else:
            return {}
    else:
        return {}


def arc_score_friend(user_id, song_id, difficulty, limit=50):
    # 得到用户好友分数表，默认最大50个
    r = []
    with Connect() as c:
        c.execute('''select user_id from best_score where user_id in (select :user_id union select user_id_other from friend where user_id_me = :user_id) and song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC limit :limit''', {
            'user_id': user_id, 'song_id': song_id, 'difficulty': difficulty, 'limit': limit})
        x = c.fetchall()
        if x != []:
            rank = 0
            for i in x:
                rank += 1
                y = get_score(c, i[0], song_id, difficulty)
                y['rank'] = rank
                r.append(y)

    return r


def arc_score_top(song_id, difficulty, limit=20):
    # 得到top分数表，默认最多20个，如果是负数则全部查询
    r = []
    with Connect() as c:
        if limit >= 0:
            c.execute('''select user_id from best_score where song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC limit :limit''', {
                'song_id': song_id, 'difficulty': difficulty, 'limit': limit})
        else:
            c.execute('''select user_id from best_score where song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC''', {
                'song_id': song_id, 'difficulty': difficulty})
        x = c.fetchall()
        if x != []:
            rank = 0
            for i in x:
                rank += 1
                y = get_score(c, i[0], song_id, difficulty)
                y['rank'] = rank
                r.append(y)

    return r


def arc_score_me(user_id, song_id, difficulty, limit=20):
    # 得到用户的排名，默认最大20个
    r = []
    with Connect() as c:
        c.execute('''select exists(select * from best_score where user_id = :user_id and song_id = :song_id and difficulty = :difficulty)''', {
            'user_id': user_id, 'song_id': song_id, 'difficulty': difficulty})
        if c.fetchone() == (1,):
            c.execute('''select count(*) from best_score where song_id = :song_id and difficulty = :difficulty and (score>(select score from best_score where user_id = :user_id and song_id = :song_id and difficulty = :difficulty) or (score>(select score from best_score where user_id = :user_id and song_id = :song_id and difficulty = :difficulty) and time_played > (select time_played from best_score where user_id = :user_id and song_id = :song_id and difficulty = :difficulty)) )''', {
                'user_id': user_id, 'song_id': song_id, 'difficulty': difficulty})
            x = c.fetchone()
            myrank = int(x[0]) + 1
            c.execute('''select count(*) from best_score where song_id=:a and difficulty=:b''',
                      {'a': song_id, 'b': difficulty})
            amount = int(c.fetchone()[0])

            if myrank <= 4:  # 排名在前4
                return arc_score_top(song_id, difficulty, limit)
            elif myrank >= 5 and myrank <= 9999 - limit + 4 and amount >= 10000:  # 万名内，前面有4个人
                c.execute('''select user_id from best_score where song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC limit :limit offset :offset''', {
                    'song_id': song_id, 'difficulty': difficulty, 'limit': limit, 'offset': myrank - 5})
                x = c.fetchall()
                if x != []:
                    rank = myrank - 5
                    for i in x:
                        rank += 1
                        y = get_score(c, i[0], song_id, difficulty)
                        y['rank'] = rank
                        r.append(y)

            elif myrank >= 10000:  # 万名外
                c.execute('''select user_id from best_score where song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC limit :limit offset :offset''', {
                    'song_id': song_id, 'difficulty': difficulty, 'limit': limit - 1, 'offset': 9999-limit})
                x = c.fetchall()
                if x != []:
                    rank = 9999 - limit
                    for i in x:
                        rank += 1
                        y = get_score(c, i[0], song_id, difficulty)
                        y['rank'] = rank
                        r.append(y)
                    y = get_score(c, user_id, song_id, difficulty)
                    y['rank'] = -1
                    r.append(y)
            elif amount - myrank < limit - 5:  # 后方人数不足
                c.execute('''select user_id from best_score where song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC limit :limit offset :offset''', {
                    'song_id': song_id, 'difficulty': difficulty, 'limit': limit, 'offset': amount - limit})
                x = c.fetchall()
                if x != []:
                    rank = amount - limit
                    if rank < 0:
                        rank = 0
                    for i in x:
                        rank += 1
                        y = get_score(c, i[0], song_id, difficulty)
                        y['rank'] = rank
                        r.append(y)
            else:
                c.execute('''select user_id from best_score where song_id = :song_id and difficulty = :difficulty order by score DESC, time_played DESC limit :limit offset :offset''', {
                    'song_id': song_id, 'difficulty': difficulty, 'limit': limit, 'offset': 9998-limit})
                x = c.fetchall()
                if x != []:
                    rank = 9998 - limit
                    for i in x:
                        rank += 1
                        y = get_score(c, i[0], song_id, difficulty)
                        y['rank'] = rank
                        r.append(y)

    return r


def calculate_rating(defnum, score):
    # 计算rating
    if score >= 10000000:
        ptt = defnum + 2
    elif score < 9800000:
        ptt = defnum + (score-9500000) / 300000
        if ptt < 0 and defnum != -10:
            ptt = 0
    else:
        ptt = defnum + 1 + (score-9800000) / 200000

    return ptt


def get_one_ptt(song_id, difficulty, score: int) -> float:
    # 单曲ptt计算，ptt为负说明没谱面定数数据
    ptt = -10
    with Connect('./database/arcsong.db') as c:
        if difficulty == 0:
            c.execute('''select rating_pst from songs where sid = :sid;''', {
                'sid': song_id})
        elif difficulty == 1:
            c.execute('''select rating_prs from songs where sid = :sid;''', {
                'sid': song_id})
        elif difficulty == 2:
            c.execute('''select rating_ftr from songs where sid = :sid;''', {
                'sid': song_id})
        elif difficulty == 3:
            c.execute('''select rating_byn from songs where sid = :sid;''', {
                'sid': song_id})

        x = c.fetchone()
        defnum = -10  # 没在库里的全部当做定数-10
        if x is not None and x != '':
            defnum = float(x[0]) / 10
            if defnum <= 0:
                defnum = -10  # 缺少难度的当做定数-10

        ptt = calculate_rating(defnum, score)

    return ptt


def get_song_grade(x):
    # 成绩转换评级
    if x >= 9900000:  # EX+
        return 6
    elif x < 9900000 and x >= 9800000:  # EX
        return 5
    elif x < 9800000 and x >= 9500000:  # AA
        return 4
    elif x < 9500000 and x >= 9200000:  # A
        return 3
    elif x < 9200000 and x >= 8900000:  # B
        return 2
    elif x < 8900000 and x >= 8600000:  # C
        return 1
    else:
        return 0


def get_song_state(x):
    # 返回成绩状态，便于比较
    if x == 3:  # PM
        return 5
    elif x == 2:  # FC
        return 4
    elif x == 5:  # Hard Clear
        return 3
    elif x == 1:  # Clear
        return 2
    elif x == 4:  # Easy Clear
        return 1
    else:  # Track Lost
        return 0


def get_user_ptt_float(c, user_id) -> float:
    # 总ptt计算，返回浮点数

    sumr = 0
    c.execute('''select rating from best_score where user_id = :a order by rating DESC limit 30''', {
              'a': user_id})
    x = c.fetchall()
    if not Config.USE_B10_AS_R10:
        if x != []:
            for i in x:
                sumr += float(i[0])
        c.execute('''select * from recent30 where user_id = :a''',
                  {'a': user_id})
        x = c.fetchone()
        if x is not None:
            r30 = []
            s30 = []
            for i in range(1, 61, 2):
                if x[i] is not None:
                    r30.append(float(x[i]))
                    s30.append(x[i+1])
                else:
                    r30.append(0)
                    s30.append('')
            r30, s30 = (list(t)
                        for t in zip(*sorted(zip(r30, s30), reverse=True)))
            songs = []
            i = 0
            while len(songs) < 10 and i <= 29 and s30[i] != '' and s30[i] is not None:
                if s30[i] not in songs:
                    sumr += r30[i]
                    songs.append(s30[i])
                i += 1
    else:
        if x != []:
            for i in range(len(x)):
                t = float(x[i][0])
                sumr += t
                if i < 10:
                    sumr += t
    return sumr/40


def get_user_ptt(c, user_id) -> int:
    # 总ptt计算，返回4位整数，向下取整

    return int(get_user_ptt_float(c, user_id)*100)


def get_user_world_rank(c, user_id) -> int:
    # 用户世界排名计算，同时返回排名值，如果超过设定最大值，返回0

    with Connect('./database/arcsong.db') as c2:
        c2.execute(
            '''select sid, rating_ftr, rating_byn from songs''')
        x = c2.fetchall()
    if x:
        song_list_ftr = [user_id]
        song_list_byn = [user_id]
        for i in x:
            if i[1] > 0:
                song_list_ftr.append(i[0])
            if i[2] > 0:
                song_list_byn.append(i[0])

    if len(song_list_ftr) >= 2:
        c.execute('''select sum(score) from best_score where user_id=? and difficulty=2 and song_id in ({0})'''.format(
            ','.join(['?']*(len(song_list_ftr)-1))), tuple(song_list_ftr))

        x = c.fetchone()
        if x[0] is not None:
            score_sum = x[0]
        else:
            score_sum = 0

    if len(song_list_byn) >= 2:
        c.execute('''select sum(score) from best_score where user_id=? and difficulty=3 and song_id in ({0})'''.format(
            ','.join(['?']*(len(song_list_byn)-1))), tuple(song_list_byn))

        x = c.fetchone()
        if x[0] is not None:
            score_sum += x[0]
        else:
            score_sum += 0

    c.execute('''update user set world_rank_score = :b where user_id = :a''', {
              'a': user_id, 'b': score_sum})

    c.execute(
        '''select count(*) from user where world_rank_score > ?''', (score_sum,))
    x = c.fetchone()
    if x and x[0] + 1 <= Config.WORLD_RANK_MAX:
        return x[0] + 1
    else:
        return 0


def update_recent30(c, user_id, song_id, rating, is_protected):
    # 刷新r30，这里的判断方法存疑，这里的song_id结尾包含难度数字
    def insert_r30table(c, user_id, a, b):
        # 更新r30表
        c.execute('''delete from recent30 where user_id = :a''',
                  {'a': user_id})
        sql = 'insert into recent30 values(' + str(user_id)
        for i in range(0, 30):
            if a[i] is not None and b[i] is not None:
                sql = sql + ',' + str(a[i]) + ',"' + b[i] + '"'
            else:
                sql = sql + ',0,""'

        sql = sql + ')'
        c.execute(sql)

    c.execute('''select * from recent30 where user_id = :a''', {'a': user_id})
    x = c.fetchone()
    if not x:
        x = [None] * 61
        x[0] = user_id
        for i in range(2, 61, 2):
            x[i] = ''
    songs = []
    flag = True
    for i in range(2, 61, 2):
        if x[i] is None or x[i] == '':
            r30_id = 29
            flag = False
            break
        if x[i] not in songs:
            songs.append(x[i])
    if flag:
        n = len(songs)
        if n >= 11:
            r30_id = 29
        elif song_id not in songs and n == 10:
            r30_id = 29
        elif song_id in songs and n == 10:
            i = 29
            while x[i*2+2] == song_id:
                i -= 1
            r30_id = i
        elif song_id not in songs and n == 9:
            i = 29
            while x[i*2+2] == song_id:
                i -= 1
            r30_id = i
        else:
            r30_id = 29
    a = []
    b = []
    for i in range(1, 61, 2):
        a.append(x[i])
        b.append(x[i+1])

    if is_protected:
        ptt_pre = get_user_ptt_float(c, user_id)
        a_pre = [x for x in a]
        b_pre = [x for x in b]

    for i in range(r30_id, 0, -1):
        a[i] = a[i-1]
        b[i] = b[i-1]
    a[0] = rating
    b[0] = song_id

    insert_r30table(c, user_id, a, b)

    if is_protected:
        ptt = get_user_ptt_float(c, user_id)
        if ptt < ptt_pre:
            # 触发保护
            if song_id in b_pre:
                for i in range(29, -1, -1):
                    if song_id == b_pre[i] and rating > a_pre[i]:
                        # 发现重复歌曲，更新到最高rating
                        a_pre[i] = rating
                        break

            insert_r30table(c, user_id, a_pre, b_pre)
    return None


def arc_score_post(user_id, song_id, difficulty, score, shiny_perfect_count, perfect_count, near_count, miss_count, health, modifier, beyond_gauge, clear_type):
    # 分数上传，返回变化后的ptt，和世界模式变化
    ptt = None
    re = None
    with Connect() as c:
        rating = get_one_ptt(song_id, difficulty, score)
        if rating < 0:  # 没数据不会向recent30里记入
            unrank_flag = True
            rating = 0
        else:
            unrank_flag = False
        now = int(time.time() * 1000)
        # recent 更新
        c.execute('''update user set song_id = :b, difficulty = :c, score = :d, shiny_perfect_count = :e, perfect_count = :f, near_count = :g, miss_count = :h, health = :i, modifier = :j, clear_type = :k, rating = :l, time_played = :m  where user_id = :a''', {
            'a': user_id, 'b': song_id, 'c': difficulty, 'd': score, 'e': shiny_perfect_count, 'f': perfect_count, 'g': near_count, 'h': miss_count, 'i': health, 'j': modifier, 'k': clear_type, 'l': rating, 'm': now})
        # 成绩录入
        c.execute('''select score, best_clear_type from best_score where user_id = :a and song_id = :b and difficulty = :c''', {
            'a': user_id, 'b': song_id, 'c': difficulty})
        now = int(now // 1000)
        x = c.fetchone()
        if x is None:
            first_protect_flag = True  # 初见保护
            c.execute('''insert into best_score values(:a,:b,:c,:d,:e,:f,:g,:h,:i,:j,:k,:l,:m,:n)''', {
                'a': user_id, 'b': song_id, 'c': difficulty, 'd': score, 'e': shiny_perfect_count, 'f': perfect_count, 'g': near_count, 'h': miss_count, 'i': health, 'j': modifier, 'k': now, 'l': clear_type, 'm': clear_type, 'n': rating})
        else:
            first_protect_flag = False
            if get_song_state(clear_type) > get_song_state(int(x[1])):  # 状态更新
                c.execute('''update best_score set best_clear_type = :a where user_id = :b and song_id = :c and difficulty = :d''', {
                    'a': clear_type, 'b': user_id, 'c': song_id, 'd': difficulty})
            if score >= int(x[0]):  # 成绩更新
                c.execute('''update best_score set score = :d, shiny_perfect_count = :e, perfect_count = :f, near_count = :g, miss_count = :h, health = :i, modifier = :j, clear_type = :k, rating = :l, time_played = :m  where user_id = :a and song_id = :b and difficulty = :c ''', {
                    'a': user_id, 'b': song_id, 'c': difficulty, 'd': score, 'e': shiny_perfect_count, 'f': perfect_count, 'g': near_count, 'h': miss_count, 'i': health, 'j': modifier, 'k': clear_type, 'l': rating, 'm': now})
        if not unrank_flag:
            # recent30 更新
            if health == -1 or int(score) >= 9800000 or first_protect_flag:
                update_recent30(c, user_id, song_id +
                                str(difficulty), rating, True)
            else:
                update_recent30(c, user_id, song_id +
                                str(difficulty), rating, False)
        # 总PTT更新
        ptt = get_user_ptt(c, user_id)
        c.execute('''update user set rating_ptt = :a where user_id = :b''', {
            'a': ptt, 'b': user_id})

        # 世界模式判断
        c.execute('''select stamina_multiply,fragment_multiply,prog_boost_multiply from world_songplay where user_id=:a and song_id=:b and difficulty=:c''', {
            'a': user_id, 'b': song_id, 'c': difficulty})
        x = c.fetchone()
        if x:
            re = server.arcworld.world_update(
                c, user_id, song_id, difficulty, rating, clear_type, beyond_gauge, health, x[0], x[1], x[2])
            re['global_rank'] = get_user_world_rank(c, user_id)  # 更新世界排名
            re["user_rating"] = ptt
        else:
            re = {'global_rank': get_user_world_rank(
                c, user_id), 'user_rating': ptt}

    return ptt, re


def arc_score_check(user_id, song_id, difficulty, score, shiny_perfect_count, perfect_count, near_count, miss_count, health, modifier, beyond_gauge, clear_type, song_token, song_hash, submission_hash):
    # 分数校验，返回布尔值
    if shiny_perfect_count < 0 or perfect_count < 0 or near_count < 0 or miss_count < 0 or score < 0:
        return False
    if difficulty not in [0, 1, 2, 3]:
        return False

    all_note = perfect_count + near_count + miss_count
    ascore = 10000000 / all_note * \
        (perfect_count + near_count/2) + shiny_perfect_count
    if abs(ascore - score) >= 5:
        return False

    with Connect() as c:  # 歌曲谱面MD5检查，服务器没有谱面就不管了
        c.execute('''select md5 from songfile where song_id=:a and file_type=:b''', {
                  'a': song_id, 'b': int(difficulty)})
        x = c.fetchone()
        if x:
            if x[0] != song_hash:
                return False

    x = song_token + song_hash + song_id + str(difficulty) + str(score) + str(shiny_perfect_count) + str(
        perfect_count) + str(near_count) + str(miss_count) + str(health) + str(modifier) + str(clear_type)
    y = str(user_id) + song_hash
    checksum = md5(x+md5(y))
    if checksum != submission_hash:
        return False

    return True


def refresh_all_score_rating():
    # 刷新所有best成绩的rating
    error = 'Unknown error.'

    with Connect('./database/arcsong.db') as c:
        c.execute(
            '''select sid, rating_pst, rating_prs, rating_ftr, rating_byn from songs''')
        x = c.fetchall()

    if x:
        song_list = [i[0] for i in x]
        with Connect() as c:
            c.execute('''update best_score set rating=0 where song_id not in ({0})'''.format(
                ','.join(['?']*len(song_list))), tuple(song_list))
            for i in x:
                for j in range(0, 4):
                    defnum = -10  # 没在库里的全部当做定数-10
                    if i is not None:
                        defnum = float(i[j+1]) / 10
                        if defnum <= 0:
                            defnum = -10  # 缺少难度的当做定数-10

                    c.execute('''select user_id, score from best_score where song_id=:a and difficulty=:b''', {
                              'a': i[0], 'b': j})
                    y = c.fetchall()
                    if y:
                        for k in y:
                            ptt = calculate_rating(defnum, k[1])
                            if ptt < 0:
                                ptt = 0

                            c.execute('''update best_score set rating=:a where user_id=:b and song_id=:c and difficulty=:d''', {
                                      'a': ptt, 'b': k[0], 'c': i[0], 'd': j})
            error = None

    else:
        error = 'No song data.'

    return error


def arc_all_post(user_id, scores_data, clearlamps_data, clearedsongs_data, unlocklist_data, installid_data, devicemodelname_data, story_data):
    # 向云端同步，无返回
    with Connect() as c:
        now = int(time.time() * 1000)
        c.execute('''delete from user_save where user_id=:a''', {'a': user_id})
        c.execute('''insert into user_save values(:a,:b,:c,:d,:e,:f,:g,:h,:i)''', {
            'a': user_id, 'b': scores_data, 'c': clearlamps_data, 'd': clearedsongs_data, 'e': unlocklist_data, 'f': installid_data, 'g': devicemodelname_data, 'h': story_data, 'i': now})
    return None


def arc_all_get(user_id):
    # 从云端同步，返回字典

    scores_data = []
    clearlamps_data = []
    clearedsongs_data = []
    unlocklist_data = []
    installid_data = ''
    devicemodelname_data = ''
    story_data = []
    createdAt = 0

    with Connect() as c:
        c.execute('''select * from user_save where user_id=:a''',
                  {'a': user_id})
        x = c.fetchone()

        if x:
            scores_data = json.loads(x[1])[""]
            clearlamps_data = json.loads(x[2])[""]
            clearedsongs_data = json.loads(x[3])[""]
            unlocklist_data = json.loads(x[4])[""]
            installid_data = json.loads(x[5])["val"]
            devicemodelname_data = json.loads(x[6])["val"]
            story_data = json.loads(x[7])[""]
            if x[8]:
                createdAt = int(x[8])

    if Config.SAVE_FULL_UNLOCK:
        installid_data = "0fcec8ed-7b62-48e2-9d61-55041a22b123"
        story_data = Constant.story_data
        unlocklist_data = Constant.unlocklist_data

    return {
        "user_id": user_id,
        "story": {
            "": story_data
        },
        "devicemodelname": {
            "val": devicemodelname_data
        },
        "installid":  {
            "val": installid_data
        },
        "unlocklist": {
            "": unlocklist_data
        },
        "clearedsongs": {
            "": clearedsongs_data
        },
        "clearlamps": {
            "": clearlamps_data
        },
        "scores": {
            "": scores_data
        },
        "version": {
            "val": 1
        },
        "createdAt": createdAt
    }
