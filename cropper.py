from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np


_DEFAULT_MEAN_LANDMARKS = np.array([[-0.46911814, -0.51348481],
                                    [0.45750203, -0.53173911],
                                    [-0.00499168, 0.06126145],
                                    [-0.40616926, 0.46826089],
                                    [0.42776873, 0.45444013]])


def _get_mid_points_5pts(landmarks):
    left_eye = landmarks[0]
    right_eye = landmarks[1]
    nose = landmarks[2]
    left_mouth = landmarks[3]
    right_mouth = landmarks[4]

    left = (left_eye + nose + left_mouth) / 3.0
    right = (right_eye + nose + right_mouth) / 3.0
    top = (left_eye + nose + right_eye) / 3.0
    bottom = (left_mouth + nose + right_mouth) / 3.0
    top_mid = (top + left + right) / 3.0
    bottom_mid = (bottom + left + right) / 3.0
    mid = (top_mid + bottom_mid) / 2.0

    return np.array([left, right, top, bottom, mid])


def align_crop_5pts_opencv(img,
                           src_landmarks,
                           mean_landmarks=_DEFAULT_MEAN_LANDMARKS,
                           crop_size=512,
                           face_factor=0.65,
                           landmark_factor=0.35,
                           align_type='similarity',
                           order=3,
                           mode='edge'):
    """Align and crop a face image by 5 landmarks.

    Arguments:
        img             : Face image to be aligned and cropped.
        src_landmarks   : 5 landmarks:
                              [[left_eye_x, left_eye_y],
                               [right_eye_x, right_eye_y],
                               [nose_x, nose_y],
                               [left_mouth_x, left_mouth_y],
                               [right_mouth_x, right_mouth_y]].
        mean_landmarks  : Mean shape, should be normalized in [-0.5, 0.5].
        crop_size       : Output image size.
        face_factor     : The factor of face area relative to the output image.
        landmark_factor : The factor of landmarks' area relative to the face.
        align_type      : 'similarity' or 'affine'.
        order           : The order of interpolation. The order has to be in the range 0-5:
                              - 0: INTER_NEAREST
                              - 1: INTER_LINEAR
                              - 2: INTER_AREA
                              - 3: INTER_CUBIC
                              - 4: INTER_LANCZOS4
                              - 5: INTER_LANCZOS4
        mode            : One of ['constant', 'edge', 'symmetric', 'reflect', 'wrap'].
                          Points outside the boundaries of the input are filled according
                          to the given mode.
    """
    import cv2
    inter = {0: cv2.INTER_NEAREST, 1: cv2.INTER_LINEAR, 2: cv2.INTER_AREA,
             3: cv2.INTER_CUBIC, 4: cv2.INTER_LANCZOS4, 5: cv2.INTER_LANCZOS4}
    border = {'constant': cv2.BORDER_CONSTANT, 'edge': cv2.BORDER_REPLICATE,
              'symmetric': cv2.BORDER_REFLECT, 'reflect': cv2.BORDER_REFLECT101,
              'wrap': cv2.BORDER_WRAP}

    assert align_type in ['affine', 'similarity'], "Only 'similarity' or 'affine' transform is allowed!"

    # move
    move = np.array([img.shape[1] // 2, img.shape[0] // 2])

    # pad border
    v_border = img.shape[0] - crop_size
    w_border = img.shape[1] - crop_size
    if v_border < 0:
        v_half = (-v_border + 1) // 2
        img = np.pad(img, ((v_half, v_half), (0, 0), (0, 0)), mode=mode)
        src_landmarks += np.array([0, v_half])
        move += np.array([0, v_half])
    if w_border < 0:
        w_half = (-w_border + 1) // 2
        img = np.pad(img, ((0, 0), (w_half, w_half), (0, 0)), mode=mode)
        src_landmarks += np.array([w_half, 0])
        move += np.array([w_half, 0])

    # estimate transform matrix
    mean_landmarks -= np.array([mean_landmarks[0, :] + mean_landmarks[1, :]]) / 2.0  # middle point of eyes as center
    trg_landmarks = mean_landmarks * (crop_size * face_factor * landmark_factor) + move

    # trg = _get_mid_points_5pts(trg_landmarks)
    # src = _get_mid_points_5pts(src_landmarks)
    trg = trg_landmarks
    src = src_landmarks
    if align_type == 'affine':
        tform = cv2.estimateAffine2D(trg, src, ransacReprojThreshold=np.Inf)[0]
    else:
        tform = cv2.estimateAffinePartial2D(trg, src, ransacReprojThreshold=np.Inf)[0]

    # warp image by given transform
    output_shape = (crop_size // 2 + move[1] + 1, crop_size // 2 + move[0] + 1)
    img_align = cv2.warpAffine(img, tform, output_shape[::-1], flags=cv2.WARP_INVERSE_MAP + inter[order], borderMode=border[mode])

    # crop
    img_crop = img_align[-crop_size:, -crop_size:]

    return img_crop


def align_crop_5pts_skimage(img,
                            src_landmarks,
                            mean_landmarks=_DEFAULT_MEAN_LANDMARKS,
                            crop_size=512,
                            face_factor=0.65,
                            landmark_factor=0.35,
                            align_type='similarity',
                            order=3,
                            mode='edge'):
    """Align and crop a face image by 5 landmarks.

    Arguments:
        img             : Face image to be aligned and cropped.
        src_landmarks   : 5 landmarks:
                              [[left_eye_x, left_eye_y],
                               [right_eye_x, right_eye_y],
                               [nose_x, nose_y],
                               [left_mouth_x, left_mouth_y],
                               [right_mouth_x, right_mouth_y]].
        mean_landmarks  : Mean shape, should be normalized in [-0.5, 0.5].
        crop_size       : Output image size.
        face_factor     : The factor of face area relative to the output image.
        landmark_factor : The factor of landmarks' area relative to the face.
        align_type      : 'similarity' or 'affine'.
        order           : The order of interpolation. The order has to be in the range 0-5:
                              - 0: Nearest-neighbor
                              - 1: Bi-linear
                              - 2: Bi-quadratic
                              - 3: Bi-cubic
                              - 4: Bi-quartic
                              - 5: Bi-quintic
        mode            : One of ['constant', 'edge', 'symmetric', 'reflect', 'wrap'].
                          Points outside the boundaries of the input are filled according
                          to the given mode.
    """
    import skimage.transform as transform

    assert align_type in ['affine', 'similarity'], "Only 'similarity' or 'affine' transform is allowed!"

    # move
    move = np.array([img.shape[1] // 2, img.shape[0] // 2])

    # pad border
    v_border = img.shape[0] - crop_size
    w_border = img.shape[1] - crop_size
    if v_border < 0:
        v_half = (-v_border + 1) // 2
        img = np.pad(img, ((v_half, v_half), (0, 0), (0, 0)), mode=mode)
        src_landmarks += np.array([0, v_half])
        move += np.array([0, v_half])
    if w_border < 0:
        w_half = (-w_border + 1) // 2
        img = np.pad(img, ((0, 0), (w_half, w_half), (0, 0)), mode=mode)
        src_landmarks += np.array([w_half, 0])
        move += np.array([w_half, 0])

    # estimate transform matrix
    mean_landmarks -= np.array([mean_landmarks[0, :] + mean_landmarks[1, :]]) / 2.0  # middle point of eyes as center
    trg_landmarks = mean_landmarks * (crop_size * face_factor * landmark_factor) + move

    # trg = _get_mid_points_5pts(trg_landmarks)
    # src = _get_mid_points_5pts(src_landmarks)
    trg = trg_landmarks
    src = src_landmarks
    tform = transform.estimate_transform(align_type, trg, src)

    # warp image by given transform
    output_shape = (crop_size // 2 + move[1] + 1, crop_size // 2 + move[0] + 1)
    img_align = transform.warp(img, tform, output_shape=output_shape, order=order, mode=mode)

    # crop
    img_crop = img_align[-crop_size:, -crop_size:]

    return img_crop