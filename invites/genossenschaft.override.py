def override(account):
    AccountInformation = type(account)
    account = account._asdict()

    if 'genossenschaft' not in account['group']:
        account['group'].append('genossenschaft')

    if account['email'] == 'vorstandsbuero@psd-hannover.de':
        account['username'] = 'psd-bank-hannover'
        account['vorname'] = 'PSD Bank'
        account['nachname'] = 'Hannover'

    if account['email'] == 'eva.george@htp-tel.de':
        account['nachname'] = 'George'

    return AccountInformation(**account)

