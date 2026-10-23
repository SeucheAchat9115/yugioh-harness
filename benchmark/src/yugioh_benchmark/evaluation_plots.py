"""Four KPI/overall panels each for observed latency and known USD cost."""
import json
from pathlib import Path
from .kpis import KPI_NAMES

LABELS = ('State recreation', 'Human-move agreement', 'Rule correctness', 'Equal-weight final score')

def comparison_points(comparison, cost_scope='evaluation'):
    if cost_scope not in {'evaluation','pipeline'}:
        raise ValueError('Cost scope must be evaluation or pipeline')
    reports=comparison.get('reports',[])
    if not reports:raise ValueError('At least one report is required')
    first=reports[0]
    for report in reports:
        if (report['protocol_sha256']!=first['protocol_sha256']
                or report['prompt_manifest']!=first['prompt_manifest']
                or report['score']['suite_sha256']!=first['score']['suite_sha256']):
            raise ValueError('Comparisons require identical protocol, prompts, suite and harness')
        if report['score']['weights']!=first['score']['weights']:
            raise ValueError('Comparisons require identical KPI weights')
    points=[]
    for report in reports:
        score=report['score']
        scores=[None if score['kpis'][key]['score'] is None else score['kpis'][key]['score']*100 for key in KPI_NAMES]
        points.append({'model':report['model'],'accuracy_percent':scores+[score['final_score_percent']],
            'evaluation_minutes':report['measurement_summary']['evaluation']['total_call_seconds']/60,
            'cost_usd':report['measurement_summary'][cost_scope]['cost_usd'],
            'measurement_summary':report['measurement_summary'], 'wall_seconds':report['wall_seconds']})
    return points

def plot_comparison(comparison, output, *, cost_scope='evaluation'):
    points=comparison_points(comparison,cost_scope)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=Path(output)
    if output.exists():raise ValueError('Use a new plot directory')
    output.mkdir(parents=True)
    files=[]
    for axis in ('runtime','cost'):
        fig,panels=plt.subplots(2,2,figsize=(11,8),layout='constrained')
        for i,panel in enumerate(panels.flat):
            missing=[]
            for n,point in enumerate(points):
                x=point['evaluation_minutes'] if axis=='runtime' else point['cost_usd']
                y=point['accuracy_percent'][i]
                if x is None or y is None:
                    missing.append(point['model']+(': grading pending' if y is None else ': cost unavailable'))
                    continue
                panel.scatter(float(x),y,label=point['model'],s=80,color=f'C{n%10}')
                panel.annotate(point['model'],(float(x),y),xytext=(6,5),textcoords='offset points',fontsize=9)
            panel.set(title=LABELS[i],ylim=(-3,107),ylabel='Accuracy (%)',
                xlabel='Total evaluated-model call time (minutes)' if axis=='runtime' else f'{cost_scope.capitalize()} cost (USD; reported or price-book estimated)')
            panel.grid(alpha=.25)
            panel.margins(x=.25)
            if missing:panel.text(.02,.03,'\n'.join(missing),transform=panel.transAxes,fontsize=9)
        fig.suptitle('Fixed reviewed checkpoints — identical archived prompts\n'+
            ('Observed transport time includes network/startup; referee time tracked separately.' if axis=='runtime'
             else 'Unavailable costs are omitted; token use and evaluation/referee totals are saved alongside.'))
        for extension in ('png','svg'):
            path=output/f'performance-{axis}.{extension}';fig.savefig(path,dpi=170);files.append(str(path))
        plt.close(fig)
    (output/'measurements.json').write_text(json.dumps({'cost_scope':cost_scope,'points':points},indent=2)+'\n',encoding='utf-8')
    return {'files':files,'measurements':str(output/'measurements.json')}
