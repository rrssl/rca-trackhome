import numpy as np
import pandas as pd


def transform_xy(points, transforms, center):
    # Rotate xy
    angle = np.radians(transforms['r'])
    cos_angle = np.cos(angle)
    sin_angle = np.sin(angle)
    points_x_rot = (
        (points['x'] - center['x'])*cos_angle
        - (points['y'] - center['y'])*sin_angle
        + center['x']
    )
    points_y_rot = (
        (points['x'] - center['x'])*sin_angle
        + (points['y'] - center['y'])*cos_angle
        + center['y']
    )
    # Scale and translate xy
    points_x_final = points_x_rot*transforms['s'] + transforms['tx']
    points_y_final = points_y_rot*transforms['s'] + transforms['ty']
    return points_x_final, points_y_final


def get_anchors(profile: dict) -> pd.DataFrame:
    """Build a dataframe of anchors with original and floorplan coordinates."""
    anchors = pd.DataFrame.from_dict(
        data=profile['anchors'],
        orient='index',
        dtype=float,
        columns=['x', 'y', 'z']
    )
    anchors['floor'] = ""
    for floor, floor_anchors in profile['floors'].items():
        for fa in floor_anchors:
            anchors.loc[fa, 'floor'] = floor
    anchors[['tx', 'ty', 's', 'r']] = anchors.apply(
        lambda row: profile['transforms'][row['floor']],
        axis=1,
        result_type='expand'
    )
    # Mirror y
    anchors_xy = anchors[['x', 'y']].copy()
    anchors_xy['y'] = anchors_xy['y'].max() - anchors_xy['y']  # swap y axis
    center = {'x': anchors['x'].mean(), 'y': anchors['y'].mean()}
    anchors['xi'], anchors['yi'] = transform_xy(
        anchors_xy,
        anchors[['tx', 'ty', 's', 'r']],
        center
    )
    return anchors


def get_recording(
    record_path: str,
    profile: dict,
    anchors: pd.DataFrame,
    denoise_period: int = None,
    interp_period: int = None
) -> pd.DataFrame:
    """Load, clean and transform the recording to overlay on the floorplan."""
    record = pd.read_csv(record_path)
    record = record[record['i'].isin(profile['tags'])]
    record = record.set_index(
        pd.to_datetime(
            record['t'], unit='ms', utc=True
        ).dt.tz_convert(profile['timezone'])
    )
    record = record.between_time(*profile['time_range'])
    record = record.drop(  # remove points at (0, 0)
        record[(record['x'] == 0) & (record['y'] == 0)].index
    )
    record = record.drop(  # remove points below ground level
        record[record['z'] <= 0].index
    )
    tags_record = []
    for tag, tag_record in record.groupby('i'):  # tag-specific cleaning
        # Remove duplicates. After analysing the points it seems fair to
        # assume that almost all duplicates are the result of the tag losing
        # an anchor or being picked up by both devices.
        tag_record = tag_record.drop_duplicates(subset=['x', 'y', 'z'])
        # First denoise by averaging over time windows.
        tag_record = tag_record.sort_index()
        if denoise_period is not None:
            tag_record = tag_record[['x', 'y', 'z']].resample(
                f'{denoise_period}s'
            ).mean().dropna()
        # Then interpolate to match the target period.
        if interp_period is not None:
            tag_record = tag_record[['x', 'y', 'z']].resample(
                f'{interp_period}s'
            ).interpolate('time', limit=2).dropna()
        # Save records.
        tag_record['i'] = tag
        tags_record.append(tag_record)
    record = pd.concat(
        tags_record
    ).set_index('i', append=True).sort_index()
    # pandasgui.show(record)
    # Assign locations to a floor.
    if len(profile['floors']) > 1:
        floor_maxima = {
            floor: max(profile['anchors'][fa][2] for fa in floor_anchors)
            for floor, floor_anchors in profile['floors'].items()
        }
        record['floor'] = ""
        for floor, floor_max in sorted(
                floor_maxima.items(), key=lambda it: it[1], reverse=True):
            # The floor name corresponds to the device on that floor.
            # Exclude points above the highest anchor.
            record.loc[
                (record['msg_sender'] == floor) & (record['z'] < floor_max+200),
                'floor'
            ] = floor
        record = record.drop(record[record['floor'] == ""].index)
    else:
        record['floor'] = next(iter(profile['floors']))
    # Change coordinates depending on the floor.
    record['y'] = anchors['y'].max() - record['y']  # swap y axis
    record[['tx', 'ty', 's', 'r']] = pd.DataFrame(
        record['floor'].map(profile['transforms']).to_list(),
        index=record.index,
    )
    # Rotate using the center of the anchors.
    center = {'x': anchors['x'].mean(), 'y': anchors['y'].mean()}
    record['x'], record['y'] = transform_xy(
        record[['x', 'y']],
        record[['tx', 'ty', 's', 'r']],
        center
    )
    # record[['x', 'y']] = record[['x', 'y']].multiply(data_xforms[:, 2:])
    # record[['x', 'y']] = record[['x', 'y']].add(data_xforms[:, :2])

    return record
