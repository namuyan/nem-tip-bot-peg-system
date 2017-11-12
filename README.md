nem-tip-bot peg system
======================

TipnemでETH系暗号通貨のペグトークンを相互に交換するシステム  
WS APIを用いたユースケース\(\)。

## グローバルなルール
* EtherInterfaceで入出力する16進数の先頭には `0x` を付ける。
* サブクラスからサブクラスを参照する動作は参照される側のLockでスレッドセーフにする。

## 使い方
##### 【概要】
2~3か月前にNekoniumという日本産のETH系の暗号通貨が発表されました。この暗号通貨は取引所上場を防ぐ為に大量にプリマインが
存在し、確かについ最近まで上場されませんでした。そこで非上場通貨ならペグトークンを作成しても問題なかろうということで
Tipnemを用いたペクトークン発行システムを構築していました。しかし、一週間前にcsさんがチカラワザで上場させてしまい公開が
難しくなりました。そこで非公開テスターという形で運営させて貰いたく、このように応募者を募り今に至ります。
* 流通ペグトークン：15000 namuyan:nekonium
* ペグ交換システム

##### 【入金】  
ここはちょっと複雑です。
1. `tag amount & deposit address` より `Tag amount` を入金元のアドレスから入金します。
2. 一分ほど待ち `tag address` に入金元アドレスが存在するのを確認します。
3. 表示されたら入金元のアドレスより任意の金額を入金して下さい。
4. 入金元アドレスはいくらでも追加できます。
5. 一度アドレスとユーザーを固定したら変更できません。

##### 【出金】(小数点以下６桁まで)
1. withdraw now!を操作し任意のアドレスに出金できます。

##### 【ペグ交換】(小数点以下１桁まで)
1. ペグトークンを `@nekopeg` に投げると残高に反映されます。  
    Ex. `@tipnem tip @nekopeg 5 nuko`
2. convert now!より、`NUKO` をペグトークンに交換できます。
    ※ペグトークンの残高以上の交換は受け付けていません。

## リンク
* [ペグシステム](http://cdn-ak.f.st-hatena.com/images/fotolife/s/s54kan/20080716/20080716004919.png)
* [アドレス作成](http://www.nukowallet.com/)
* [INSTALL](INSTALL.md)
* [Tipnem](https://namuyan.github.io/nem-tip-bot/index)

## 履歴
* 2017/11/12 非公開テスト開始
