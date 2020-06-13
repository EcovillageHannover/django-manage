from django.http import HttpResponse
from django.shortcuts import render

from poll.models import *

def index(request):
    pcs = PollCollection.list_for_user(request.user)
    unvoted = [len(pc.get_unvoted(request.user)) for pc in pcs]
    unvoted = [x for x in unvoted if x]
    context = {
        'unvoted_polls': sum(unvoted),
        'unvoted_pcs': len(unvoted),
    }
    return render(request, 'index.html', context)
