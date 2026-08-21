from django.contrib.staticfiles import finders


def test_icone_de_atalho_existe_nas_origens_estaticas():
    assert finders.find("ds/logos/icone-192.png") is not None
