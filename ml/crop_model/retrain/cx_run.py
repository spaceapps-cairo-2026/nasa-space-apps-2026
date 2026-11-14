"""Run the cx variants. Usage: python cx_run.py <group> [<group> ...]   (groups defined in VARIANTS)."""
import sys

import evalx as E
from cx_strategies import CX, CXCrop

VARIANTS = {
    # --- one knob at a time
    'A': {
        'cx-00-repro': dict(),
        'cx-01-irr90': dict(irr_thr=0.9),
        'cx-02-irr80': dict(irr_thr=0.8),
        'cx-03-irr50': dict(irr_thr=0.5),
        'cx-04-dirr80': dict(dry_irr_thr=0.8),
        'cx-05-dirr50': dict(dry_irr_thr=0.5),
        'cx-06-unf150': dict(unf_rain=150),
        'cx-07-unf200': dict(unf_rain=200),
        'cx-08-unf250': dict(unf_rain=250),
        'cx-09-unf300': dict(unf_rain=300),
        'cx-10-w2': dict(cw=2),
        'cx-11-w5': dict(cw=5),
        'cx-12-w10': dict(cw=10),
        'cx-13-w20': dict(cw=20),
        'cx-14-w5-renorm': dict(cw=5, mode='renorm'),
        'cx-15-w20-renorm': dict(cw=20, mode='renorm'),
        'cx-16-group0.5': dict(mode='group', group_frac=0.5),
        'cx-17-group1': dict(mode='group', group_frac=1.0),
    },
    # --- heavy weight only where it is really dry
    'B': {
        'cx-20-w5lt100': dict(cw=5, cw_rain=100),
        'cx-21-w10lt100': dict(cw=10, cw_rain=100),
        'cx-22-w20lt100': dict(cw=20, cw_rain=100),
        'cx-23-unf150-w5lt150': dict(unf_rain=150, cw=5, cw_rain=150),
        'cx-24-unf150-w10lt150': dict(unf_rain=150, cw=10, cw_rain=150),
        'cx-25-unf150-w10lt100': dict(unf_rain=150, cw=10, cw_rain=100),
        'cx-26-dirr80-w10lt100': dict(dry_irr_thr=0.8, cw=10, cw_rain=100),
        'cx-27-irr90-w10lt100': dict(irr_thr=0.9, cw=10, cw_rain=100),
        'cx-28-unf200-ramp10-100-200': dict(unf_rain=200, cw=10, ramp=(100, 200)),
        'cx-29-unf200-ramp10-50-150': dict(unf_rain=200, cw=10, ramp=(50, 150)),
        'cx-30-unf250-ramp10-100-250': dict(unf_rain=250, cw=10, ramp=(100, 250)),
        'cx-31-unf150-ramp20-75-150': dict(unf_rain=150, cw=20, ramp=(75, 150)),
        'cx-32-unf150-dirr80-w10lt100': dict(unf_rain=150, dry_irr_thr=0.8, cw=10, cw_rain=100),
        'cx-33-unf150-dirr80@150-w10lt150': dict(unf_rain=150, dry_irr_thr=0.8, dry_rain=150, cw=10, cw_rain=150),
    },
    # --- crop-aware exemption (kind='crop')
    'C': {
        'cx-40-crop-unf250-w5lt250': dict(kind='crop', unf_rain=250, cw=5, cw_rain=250),
        'cx-41-crop-unf250-w10lt250': dict(kind='crop', unf_rain=250, cw=10, cw_rain=250),
        'cx-42-crop-unf300-w5lt300': dict(kind='crop', unf_rain=300, cw=5, cw_rain=300),
        'cx-43-crop-unf250-dirr80-w5lt250': dict(kind='crop', unf_rain=250, dry_irr_thr=0.8, cw=5, cw_rain=250),
        'cx-44-crop-unf250-w5lt250-p33': dict(kind='crop', unf_rain=250, cw=5, cw_rain=250, exempt_prev=1 / 3),
        'cx-45-crop-unf250-w5lt250-p50': dict(kind='crop', unf_rain=250, cw=5, cw_rain=250, exempt_prev=0.5),
        'cx-46-crop-unf250-w2lt250': dict(kind='crop', unf_rain=250, cw=2, cw_rain=250),
        'cx-47-crop-unf250-w1': dict(kind='crop', unf_rain=250),
    },
    'D': {
        'cx-50-crop-unf250-w3lt250': dict(kind='crop', unf_rain=250, cw=3, cw_rain=250),
        'cx-51-crop-unf250-dirr80-w2lt250': dict(kind='crop', unf_rain=250, dry_irr_thr=0.8, cw=2, cw_rain=250),
        'cx-52-crop-unf250-w5lt100': dict(kind='crop', unf_rain=250, cw=5, cw_rain=100),
        'cx-53-crop-unf250-w10lt100': dict(kind='crop', unf_rain=250, cw=10, cw_rain=100),
        'cx-54-crop-unf250-ramp5-100-250': dict(kind='crop', unf_rain=250, cw=5, ramp=(100, 250)),
        'cx-55-crop-unf250-ramp10-50-200': dict(kind='crop', unf_rain=250, cw=10, ramp=(50, 200)),
        'cx-56-crop-unf200-w3lt200': dict(kind='crop', unf_rain=200, cw=3, cw_rain=200),
        'cx-57-crop-unf300-w2lt300': dict(kind='crop', unf_rain=300, cw=2, cw_rain=300),
        'cx-58-crop-unf250-w3lt250-p33': dict(kind='crop', unf_rain=250, cw=3, cw_rain=250, exempt_prev=1 / 3),
        'cx-59-crop-unf250-w2lt250-p33': dict(kind='crop', unf_rain=250, cw=2, cw_rain=250, exempt_prev=1 / 3),
        'cx-60-crop-unf250-w3lt250-min0': dict(kind='crop', unf_rain=250, cw=3, cw_rain=250, exempt_min_rain=0),
        'cx-61-crop-unf300-w3lt300-p33': dict(kind='crop', unf_rain=300, cw=3, cw_rain=300, exempt_prev=1 / 3),
    },
    'F': {
        'cx-62-crop-unf250-w2.5lt250-p33': dict(kind='crop', unf_rain=250, cw=2.5, cw_rain=250, exempt_prev=1 / 3),
        'cx-63-crop-unf250-w3lt250-p25': dict(kind='crop', unf_rain=250, cw=3, cw_rain=250, exempt_prev=0.25),
        'cx-64-crop-unf250-w4lt250-p25': dict(kind='crop', unf_rain=250, cw=4, cw_rain=250, exempt_prev=0.25),
        'cx-65-crop-unf250-dirr80-w3lt250-p33': dict(kind='crop', unf_rain=250, dry_irr_thr=0.8, cw=3, cw_rain=250, exempt_prev=1 / 3),
        'cx-66-crop-unf250-dirr80-w2lt250-p33': dict(kind='crop', unf_rain=250, dry_irr_thr=0.8, cw=2, cw_rain=250, exempt_prev=1 / 3),
    },
}


def build(kw):
    kw = dict(kw)
    return (CXCrop if kw.pop('kind', None) == 'crop' else CX)(**kw)


if __name__ == "__main__":
    for g in sys.argv[1:]:
        for name, kw in VARIANTS[g].items():
            E.run(build(kw), name)
