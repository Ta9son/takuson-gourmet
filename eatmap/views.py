from django.shortcuts import render, redirect
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, TemplateView
from django.contrib.auth import login, authenticate
from .models import Pref, Category, Review
from .forms import SearchForm, SignUpForm, LoginForm, ReviewForm
from django.contrib.auth.views import LoginView, LogoutView
import json
import requests
from django.db.models import Avg
from django.contrib import messages





def get_keyid():
    return "d345b8b9b46b3476887742e30468a2bf"


class IndexView(TemplateView):
    template_name = 'eatmap/index.html'

    def get_context_data(self, *args, **kwargs):
        searchform = SearchForm()
        
        query = get_gnavi_data('','','PREF11','ディナー',15)
        res_list = rest_search(query)
        pickup_list = extract_restaurant_info(res_list)
        review_list = Review.objects.all()[:10]
        params = {
            'searchform': searchform,
            'pickup_list': pickup_list,
            'review_list': review_list,

            }
        return params


def Search(request):
    if request.method == 'GET':
        searchform = SearchForm(request.POST)

        if searchform.is_valid():
            category_l = request.GET['category_l']
            pref = request.GET['pref']
            freeword = request.GET['freeword']
            query = get_gnavi_data("", category_l, pref, freeword, 10)
            res_list = rest_search(query)
            total_hit_count = len(res_list)
            # 4. 整形した情報をリスト形式で保存し、paramsの一要素として渡す
            restaurants_info = extract_restaurant_info(res_list)

    params = {
        'total_hit_count': total_hit_count,
        'restaurants_info': restaurants_info,
        }

    return render (request, 'eatmap/search.html', params)


def get_gnavi_data(id, category_l, pref, freeword, hit_per_page):
    keyid = get_keyid()
    # 一度に取得できる最大件数
    hit_per_page = hit_per_page
    # 店舗のid（グルナビ内で一意になっている）
    id = id
    # 大業態カテゴリ
    category_l = category_l
    #pref
    pref = pref
    #Freeword
    freeword = freeword
    #今回は関東地方のみ（コール回数を少なくするため）
    area = "AREA110"
    #パラメータ設定
    query = {"keyid": keyid, "id":id, "area":area, "pref":pref, "category_l":category_l,"hit_per_page":hit_per_page, "freeword":freeword}

    return query


def rest_search(query):
    res_list = []
    res = json.loads(requests.get("https://api.gnavi.co.jp/RestSearchAPI/v3/", params=query).text)
    # レスポンスがerror でない場合に処理を開始する
    if "error" not in res:
        # print(f'res------->{res}')
        res_list.extend(res["rest"])
    return res_list


def extract_restaurant_info(restaurants: 'restaurant response') -> 'restaurant list':
    restaurant_list = []
    for restaurant in restaurants:
        id = restaurant["id"]
        name = restaurant["name"]
        name_kana = restaurant["name_kana"]
        url = restaurant["url"]
        url_mobile = restaurant["url_mobile"]
        shop_image1 = restaurant["image_url"]["shop_image1"]
        shop_image2 = restaurant["image_url"]["shop_image2"]
        address = restaurant["address"]
        tel = restaurant["tel"]
        station_line = restaurant["access"]["line"]
        station = restaurant["access"]["station"]
        latitude = restaurant["latitude"]
        longitude = restaurant["longitude"]
        pr_long = restaurant["pr"]["pr_long"]

        restaurant_list.append([id, name, name_kana, url, url_mobile, shop_image1, shop_image2, address, tel, station_line, station, latitude, longitude, pr_long])
        # 確認用
        print(f'restaurnt_list--------->{restaurant_list}')

    return restaurant_list



# ショップの詳細
def ShopInfo(request, restid):
    keyid = get_keyid()
    id = restid
    query = get_gnavi_data(id, "", "", "", 1)
    res_list = rest_search(query)
    restaurants_info = extract_restaurant_info(res_list)

    # 以下を追加、編集　ここから
    review_count = Review.objects.filter(shop_id=restid).count()
    score_ave = Review.objects.filter(shop_id = restid).aggregate(Avg('score'))

    #print('score_ave--------------', score_ave)
    """
     ↑の出力
     score_ave-------------- {'score__avg': 4.0}
     辞書型になっている。
     """

    average = score_ave['score__avg']

    #print('average----------', average)
    """
    ↑の出力
    average---------- 4.0
    
    """


    if average:
        average_rate = average / 5 * 100
    else:
        average_rate = 0

    if request.method == 'GET':
        review_form = ReviewForm()
        review_list = Review.objects.filter(shop_id = restid)

    else:
        form = ReviewForm(data=request.POST)
        score = request.POST['score']
        comment = request.POST['comment']

        if form.is_valid():
            review = Review()
            review.shop_id = restid
            review.shop_name = restaurants_info[0][1]
            review.shop_kana = restaurants_info[0][2]
            review.shop_address = restaurants_info[0][7]
            review.image_url = restaurants_info[0][5]
            review.user = request.user
            review.score = score
            review.comment = comment

            is_exist = 0
            is_exist = Review.objects.filter(shop_id=review.shop_id).filter(user=review.user).count()

            if not is_exist == 0:
                messages.error(request, '既にレビューを投稿済みです。')
                return redirect('eatmap:shop_info', restid)
            else:
                review.save()
                messages.success(request, 'レビューを投稿しました。')  # 追加
                return redirect('eatmap:shop_info', restid)
        else:
            messages.error(request, 'エラーがあります。')  # 追加
            return redirect('eatmap:shop_info', restid)
        return render(request, 'eatmap/index.html', {})

    params = {
        'title': '店舗詳細',
        'review_count': review_count,
        'restaurants_info': restaurants_info,
        'review_form': review_form,
        'review_list': review_list,
        'average': average,
        'average_rate': average_rate,
        }

    return render (request, 'eatmap/shop_info.html', params)
    # 以下を追加、編集　ここまで



# ユーザーの新規登録
class SignUp(CreateView):
    form_class =  SignUpForm
    template_name = 'eatmap/signup.html'

    def post(self, request, *args, **kwargs):
        form = self.form_class(data=request.POST)

        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request,user)
            return redirect('eatmap:index')
        return render(request, 'eatmap/signup.html', {'form':form})


# ログイン
class Login(LoginView):
    form_class = LoginForm
    template_name = 'eatmap/login.html'


# ログアウト
class Logout(LogoutView):
    template_name = 'eatmap/logout.html'


