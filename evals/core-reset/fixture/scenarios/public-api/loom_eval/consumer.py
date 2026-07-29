from loom_eval.api import User, render_user


def profile_label(user: User) -> str:
    return render_user(user)
