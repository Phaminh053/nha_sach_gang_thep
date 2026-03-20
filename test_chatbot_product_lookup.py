from app.api.backend import BackendDispatcher


def test_reference_normalization():
    dispatcher = BackendDispatcher()

    cases = [
        ('Đứa trẻ thứ sáu', 'Đứa trẻ thứ sáu'),
        ('"Đứa trẻ thứ sáu"', 'Đứa trẻ thứ sáu'),
        ('quyển sách Đứa trẻ thứ sáu', 'Đứa trẻ thứ sáu'),
        ('cuốn Đứa trẻ thứ sáu', 'Đứa trẻ thứ sáu'),
        ('thông tin về Đứa trẻ thứ sáu', 'Đứa trẻ thứ sáu'),
    ]

    for raw_value, expected in cases:
        actual = dispatcher._clean_product_reference(raw_value)
        print(f'{raw_value!r} -> {actual!r}')
        assert actual == expected, f'Expected {expected!r}, got {actual!r}'


def test_reference_candidates():
    dispatcher = BackendDispatcher()

    params = {'name': 'quyển sách Đứa trẻ thứ sáu'}
    candidates = dispatcher._build_product_reference_candidates(params)
    print(candidates)

    assert 'quyển sách Đứa trẻ thứ sáu' in candidates
    assert 'Đứa trẻ thứ sáu' in candidates


if __name__ == '__main__':
    test_reference_normalization()
    test_reference_candidates()
    print('chatbot product lookup tests passed')
